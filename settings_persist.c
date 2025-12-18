/**
 * @file settings_persist.c
 * @author 刘通达
 * @brief 本文件实现 settings_persist 模块的基本功能
 * @version 0.1.2
 * @date 2025-09-21 14:05:53
 *
 * @copyright Copyright (c) 2025
 *
 */

#include "settings_persist.h"
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "settings_persist.h"
#define SETTINGS_PERSIST_MODULE_TAG "settings_persist"
#include "settings_persist_log.h"

#include "inih-57/ini.h"

/* 配置文件路径定义 */
#if SIMULATOR
#define MAIN_SETTINGS_PATH "./settings(for_ui_simulator).ini"
#define BACKUP_SETTINGS_PATH "./settings(for_ui_simulator).bak"
#define TEMP_SETTINGS_PATH "./settings(for_ui_simulator).tmp"
#define TEMP_BACKUP_PATH "./settings_bak(for_ui_simulator).tmp"
#else
#define MAIN_SETTINGS_PATH "/userdata/settings.ini"
#define BACKUP_SETTINGS_PATH "/userdata/settings.bak"
#define TEMP_SETTINGS_PATH "/userdata/settings.tmp"
#define TEMP_BACKUP_PATH "/userdata/settings_bak.tmp"
#endif

/* 线程中while(1)每次休眠的时间(单位ms) */
#define SETTINGS_PERSIST_THREAD_LOOP_SLEEP_MS (200)
/* 静态断言检查 */
_Static_assert(
        (SETTINGS_PERSIST_THREAD_LOOP_SLEEP_MS * 1000ULL) <= UINT32_MAX,
        "SETTINGS_PERSIST_THREAD_LOOP_SLEEP_MS is too large, exceeds usleep's parameter range");
_Static_assert(SETTINGS_PERSIST_THREAD_LOOP_SLEEP_MS >= 200,
        "SETTINGS_PERSIST_THREAD_LOOP_SLEEP_MS is too small, it may cause CPU waste");
extern int settings_ini_handler(void *user, const char *section, const char *name,
                                const char *value);

extern void settings_restore_defaults(Settings *settings);

extern int write_settings_to_file(const char *filename, const Settings *settings);

/* 线程运行标志位 */
int settings_persist_thread_running = 0;
/* 对 settings_persist_thread_running 的访问和修改都要通过锁来进行 */
pthread_mutex_t settings_persist_thread_status_mutex = PTHREAD_MUTEX_INITIALIZER;
/* 线程句柄 */
static pthread_t settings_persist_thread;
/* 内部缓存的配置数据 */
Settings settings_cache;
/* 对 settings_cache 的访问和修改都要通过锁来进行 */
pthread_mutex_t cache_mutex = PTHREAD_MUTEX_INITIALIZER;
/* 上次保存的缓存快照 */
static Settings cache_snapshot;
/* 延迟写入的循环次数: 发生变化后经过多少次循环再写入到文件系统中 */
#define DELAY_WRITE_CYCLES 5

/**
 * @brief 参数模型: CRC-16/IBM x16+x15+x2+1
        宽度 (WIDTH): 16
        多项式 POLY(Hex): 8005
        初始值 INIT(Hex): 0000
        结果异或值 (XOROUT): 0x0000
        输入数据反转(REFIN): ON
        输出数据反转(REFOUT): ON
 * @param [in] data 要计算crc的数据缓冲区
 * @param [in] length 要计算crc的数据长度
 * @return CRC的计算结果
 */
static uint16_t calculate_crc_16_ibm(const uint8_t *data, size_t length)
{
    uint16_t crc = 0x0000; /* 初始值 0x0000 */

    /* 遍历输入数据的每个字节 */
    for (size_t i = 0; i < length; i++)
    {
        /* 反转当前字节的位顺序 */
        uint8_t byte = data[i];
        byte = ((byte & 0xF0) >> 4) | ((byte & 0x0F) << 4);
        byte = ((byte & 0xCC) >> 2) | ((byte & 0x33) << 2);
        byte = ((byte & 0xAA) >> 1) | ((byte & 0x55) << 1);

        /* 将反转后的字节与当前 CRC 值异或 */
        crc ^= (uint16_t)byte << 8;

        /* 对当前 CRC 值的每一位进行处理 */
        for (uint8_t j = 0; j < 8; j++)
        {
            if (crc & 0x8000)
            {
                crc = (crc << 1) ^ 0x8005;
            }
            else
            {
                crc <<= 1;
            }
        }
    }

    /* 反转最终的 CRC 结果 */
    uint16_t result = 0;
    for (int i = 0; i < 16; i++)
    {
        result <<= 1;
        result |= (crc & 1);
        crc >>= 1;
    }

    return result;
}

/**
 * @brief 计算Settings结构体的CRC16-IBM校验值(排除Settings.Verify.crc_16_ibm)
 *
 * @param[in] settings 待计算的Settings
 * @return uint16_t CRC16-IBM校验值
 */
static uint16_t calculate_settings_crc(const Settings *settings)
{
    if (!settings)
    {
        return 0;
    }

    Settings temp = *settings;
    temp.Verify.crc_16_ibm = 0; /* 排除校验字段本身 */

    /* 计算整个结构体的CRC */
    return calculate_crc_16_ibm((const uint8_t *)&temp, sizeof(Settings));
}

/**
 * @brief 从INI文件中加载并解析Settings
 *
 * @param[in] filename 文件路径
 * @param[in, out] settings 解析结果
 * @return 执行结果
 * @retval true 成功
 * @retval false 失败
 */
static bool load_from_file(const char *filename, Settings *settings)
{
    SETTINGS_PERSIST_SET_FUNC_LOG_TAG("load_from_file");
    if (!filename || !settings)
    {
        SETTINGS_PERSIST_LOG_ERROR("输入参数中含有NULL");
        return false;
    }

    settings_restore_defaults(settings);

    FILE *file = fopen(filename, "r");
    if (!file)
    {
        SETTINGS_PERSIST_LOG_ERROR("文件打开失败: %s", filename);
        return false;
    }

    int parse_result = ini_parse_file(file, settings_ini_handler, settings);
    fclose(file);

    if (parse_result != 0)
    {
        SETTINGS_PERSIST_LOG_ERROR("INI文件解析失败: %s", filename);
        return false;
    }

    uint16_t calculated = calculate_settings_crc(settings);
    SETTINGS_PERSIST_LOG_INFO("计算出来的CRC值是: 0x%04X", calculated);
    SETTINGS_PERSIST_LOG_INFO("文件中读取出来的CRC值是: 0x%04X", settings->Verify.crc_16_ibm);
    int result = calculated == settings->Verify.crc_16_ibm;
    if (result)
    {
        SETTINGS_PERSIST_LOG_INFO("%s的CRC_16_IBM校验通过", filename);
    }
    else
    {
        SETTINGS_PERSIST_LOG_ERROR("%s的CRC_16_IBM校验失败", filename);
    }
    return result;
}

/**
 * @brief Settings保存函数(会同时更新CRC并创建备份)
 *
 * @param[in] settings 需要保存的Settings
 * @return 执行结果
 * @retval true 成功
 * @retval false 失败
 */
static bool save_settings_with_crc(Settings *settings)
{
    SETTINGS_PERSIST_SET_FUNC_LOG_TAG("save_settings_with_crc");
    if (!settings)
    {
        return false;
    }

    /* 1. 计算并更新CRC */
    settings->Verify.crc_16_ibm = calculate_settings_crc(settings);

    /* 2. 先写入临时文件 */
    if (write_settings_to_file(TEMP_SETTINGS_PATH, settings) != 0)
    {
        SETTINGS_PERSIST_LOG_ERROR("临时文件%s写入失败", TEMP_SETTINGS_PATH);
        return false;
    }

    /* 3. 处理备份文件（同样使用临时文件+重命名确保完整性） */
    if (write_settings_to_file(TEMP_BACKUP_PATH, settings) == 0)
    {
        SETTINGS_PERSIST_LOG_DEBUG("临时文件%s写入成功", TEMP_BACKUP_PATH);
        rename(TEMP_BACKUP_PATH, BACKUP_SETTINGS_PATH);
    }

    /* 4. 原子替换主文件 */
    if (rename(TEMP_SETTINGS_PATH, MAIN_SETTINGS_PATH) != 0)
    {
        SETTINGS_PERSIST_LOG_ERROR("%s rename-> %s 失败, 请务必检查!!!", TEMP_SETTINGS_PATH,
                                   MAIN_SETTINGS_PATH);
        return false;
    }

    SETTINGS_PERSIST_LOG_DEBUG("保存成功");
    return true;
}

/**
 * @brief settings_persist模块 的内部工作线程
 * 此线程内部会自动处理数据发生变化时的保存(且已内置延迟写入)
 *
 * @param[in] arg 实际上无需输入参数
 * @return 实际上也无返回值
 */
static void *work_thread_func(void *arg)
{
    SETTINGS_PERSIST_SET_FUNC_LOG_TAG("work_thread_func");
    (void)arg;                       /* 暂时未使用的变量 */
    bool cache_changed = false;      /* 缓存是否发生变化的标记 */
    uint32_t change_cycle_count = 0; /* 变化后的循环计数 */

    while (1)
    {
        /* 关键修改：通过锁保护标志位的读取 */
        pthread_mutex_lock(&settings_persist_thread_status_mutex);
        int running = settings_persist_thread_running;
        pthread_mutex_unlock(&settings_persist_thread_status_mutex);
        if (!running)
        {
            break;
        }
        /* 线程循环间隔 */
        usleep(SETTINGS_PERSIST_THREAD_LOOP_SLEEP_MS * 1000);

        pthread_mutex_lock(&cache_mutex);
        /*
         * 通过内存对比检测缓存是否变化
         * @warning Settings结构内部禁止存在指针, 否则通过内存比较的方式就不可靠
         */
        bool current_changed = (memcmp(&settings_cache, &cache_snapshot, sizeof(Settings)) != 0);

        if (current_changed)
        {
            /* 检测到变化 立即更新快照并标记变化 重新计数 */
            memcpy(&cache_snapshot, &settings_cache, sizeof(Settings));
            cache_changed = true;
            change_cycle_count = 0;
            SETTINGS_PERSIST_LOG_DEBUG("检测到数据变化");
        }
        else if (cache_changed)
        {
            /* 变化后未继续修改 累加计数 */
            change_cycle_count++;
            SETTINGS_PERSIST_LOG_DEBUG("数据未继续变化, 计数+1");
        }

        /* 满足延迟条件时写入 */
        if (cache_changed && change_cycle_count >= DELAY_WRITE_CYCLES)
        {
            SETTINGS_PERSIST_LOG_DEBUG("条件满足, 准备写入文件");
            save_settings_with_crc(&settings_cache);

            /* 不管写入结果如何 都清空标志位和计数器 防止频繁操作FLASH */
            memcpy(&cache_snapshot, &settings_cache, sizeof(Settings));
            cache_changed = false;
            change_cycle_count = 0;
        }

        pthread_mutex_unlock(&cache_mutex);
    }
    return NULL;
}

/**
 * @brief 初始化 settings_persist模块
 *
 * @return 执行结果
 * @retval 1 settings_persist模块已在运行中 无需初始化
 * @retval 0 初始化成功
 * @retval -1 初始化失败: 线程启动失败
 */
int settings_persist_init(void)
{
    SETTINGS_PERSIST_SET_FUNC_LOG_TAG("settings_persist_init");
    pthread_mutex_lock(&settings_persist_thread_status_mutex);
    if (settings_persist_thread_running == 1)
    {
        /* settings_persist_thread_running 为1 认为已经初始化完成 直接返回 */
        SETTINGS_PERSIST_LOG_WARN("settings_persist模块初始化失败: 已经在运行中, 请勿重复启动!)");
        pthread_mutex_unlock(&settings_persist_thread_status_mutex);
        return 1;
    }

    /* 加载配置(优先主文件 失败则尝试备份 最后用默认值) */
    pthread_mutex_lock(&cache_mutex);
    memset(&settings_cache, 0, sizeof(Settings));
    if (!load_from_file(MAIN_SETTINGS_PATH, &settings_cache) &&
        !load_from_file(BACKUP_SETTINGS_PATH, &settings_cache))
    {
        settings_restore_defaults(&settings_cache);
        save_settings_with_crc(&settings_cache);
    }
    memcpy(&cache_snapshot, &settings_cache, sizeof(Settings)); /* 初始快照与cache完全一致 */
    pthread_mutex_unlock(&cache_mutex);

    /* 将线程运行标志位置1 */
    settings_persist_thread_running = 1;

    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setstacksize(&attr, 8 * 1024); /* 设置栈空间大小为8KBytes */

    /* 启动线程 */
    int ret = pthread_create(&settings_persist_thread, &attr, work_thread_func, NULL);
    pthread_attr_destroy(&attr);
    if (ret != 0)
    {
        settings_persist_thread_running = 0;
        SETTINGS_PERSIST_LOG_ERROR("settings_persist模块初始化失败: 线程启动失败!)");
        pthread_mutex_unlock(&settings_persist_thread_status_mutex);
        return -1;
    }

    SETTINGS_PERSIST_LOG_INFO("settings_persist模块初始化成功!)");
    pthread_mutex_unlock(&settings_persist_thread_status_mutex);
    return 0;
}

/**
 * @brief 获取 settings_persist模块 内部缓存数据
 *
 * @param[in, out] settings 获取到的结果
 * @return 执行结果
 * @retval 0 获取成功
 * @retval -1 获取失败: 输入参数为NULL
 * @retval -2 获取失败: settings_persist模块未运行
 */
int settings_persist_get_data(Settings *settings)
{
    SETTINGS_PERSIST_SET_FUNC_LOG_TAG("settings_persist_get_data");
    if (settings == NULL)
    {
        return -1;
    }

    pthread_mutex_lock(&settings_persist_thread_status_mutex);
    if (settings_persist_thread_running == 0)
    {
        SETTINGS_PERSIST_LOG_WARN("数据获取失败: settings_persist模块未初始化");
        pthread_mutex_unlock(&settings_persist_thread_status_mutex);
        return -2;
    }

    pthread_mutex_lock(&cache_mutex);
    memcpy(settings, &settings_cache, sizeof(Settings));
    pthread_mutex_unlock(&cache_mutex);
    SETTINGS_PERSIST_LOG_DEBUG("数据获取成功");
    pthread_mutex_unlock(&settings_persist_thread_status_mutex);
    return 0;
}

/**
 * @brief 更新 settings_persist模块 内部缓存数据
 *
 * @param[in] settings 最新的数据
 * @return 执行结果
 * @retval 0 更新成功
 * @retval -1 更新失败: 输入参数为NULL
 * @retval -2 更新失败: settings_persist模块未运行
 */
int settings_persist_set_data(const Settings *settings)
{
    SETTINGS_PERSIST_SET_FUNC_LOG_TAG("settings_persist_set_data");
    if (settings == NULL)
    {
        return -1;
    }

    pthread_mutex_lock(&settings_persist_thread_status_mutex);
    if (settings_persist_thread_running == 0)
    {
        SETTINGS_PERSIST_LOG_WARN("数据更新失败: settings_persist模块未初始化");
        pthread_mutex_unlock(&settings_persist_thread_status_mutex);
        return -2;
    }

    pthread_mutex_lock(&cache_mutex);
    memcpy(&settings_cache, settings, sizeof(Settings));
    pthread_mutex_unlock(&cache_mutex);
    SETTINGS_PERSIST_LOG_DEBUG("数据更新成功");
    pthread_mutex_unlock(&settings_persist_thread_status_mutex);
    return 0;
}

/**
 * @brief 销毁 settings_persist模块
 *
 * @return 执行结果
 * @retval 1 settings_persist模块未运行 无法销毁
 * @retval 0 销毁成功
 */
int settings_persist_deinit(void)
{
    SETTINGS_PERSIST_SET_FUNC_LOG_TAG("settings_persist_deinit");
    pthread_mutex_lock(&settings_persist_thread_status_mutex);
    /* 未初始化就尝试调用销毁函数 */
    if (settings_persist_thread_running == 0)
    {
        SETTINGS_PERSIST_LOG_WARN("settings_persist模块销毁失败: 模块还未初始化, 请勿重复销毁!");
        pthread_mutex_unlock(&settings_persist_thread_status_mutex);
        return 1;
    }

    settings_persist_thread_running = 0;

    /* 阻塞等待线程结束 */
    pthread_join(settings_persist_thread, NULL);

    SETTINGS_PERSIST_LOG_INFO("settings_persist模块销毁成功");
    pthread_mutex_unlock(&settings_persist_thread_status_mutex);
    return 0;
}
