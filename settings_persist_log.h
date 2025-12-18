/**
 * @file settings_persist_log.h
 * @author 刘通达
 * @brief 视频播放器日志模块 - 提供分级日志记录和函数级标签追踪功能
 *        正确使用方式: 在需要使用日志功能的.c文件开头按照以下顺序引用:
 *        #define SETTINGS_PERSIST_MODULE_TAG "YourModuleName"
 *        #include "settings_persist_log.h"
 * @warning 禁止在.h文件中引用本头文件
 * @version 0.1.1
 * @date 2025-09-07 19:55:41
 *
 * @history
 *    2025-09-07 19:55:41 [0.1.1] 刘通达 优化日志等级较高时未生效的LOG的宏定义 确保进一步降低开销
 * @copyright Copyright (c) 2025
 *
 */
#ifndef _SETTINGS_PERSIST_LOG_H
#define _SETTINGS_PERSIST_LOG_H

#include <stdio.h>

/*
 * 日志等级定义
 * 从低到高依次为: 调试 < 信息 < 警告 < 错误
 * 当日志级别设置为某一级别时, 只输出该级别及以上的日志
 */
#define SETTINGS_PERSIST_LOG_LEVEL_DEBUG (0)
#define SETTINGS_PERSIST_LOG_LEVEL_INFO (1)
#define SETTINGS_PERSIST_LOG_LEVEL_WARN (2)
#define SETTINGS_PERSIST_LOG_LEVEL_ERROR (3)

/*
 * 配置当前日志等级
 * 可根据开发阶段选择合适的日志级别:
 * - 开发调试阶段: 建议使用SETTINGS_PERSIST_LOG_LEVEL_DEBUG
 * - 测试阶段: 建议使用SETTINGS_PERSIST_LOG_LEVEL_INFO
 * - 生产环境: 建议使用SETTINGS_PERSIST_LOG_LEVEL_WARN或SETTINGS_PERSIST_LOG_LEVEL_ERROR
 */
#define SETTINGS_PERSIST_CURRENT_LOG_LEVEL SETTINGS_PERSIST_LOG_LEVEL_DEBUG
// #define SETTINGS_PERSIST_CURRENT_LOG_LEVEL SETTINGS_PERSIST_LOG_LEVEL_INFO
// #define SETTINGS_PERSIST_CURRENT_LOG_LEVEL SETTINGS_PERSIST_LOG_LEVEL_WARN
// #define SETTINGS_PERSIST_CURRENT_LOG_LEVEL SETTINGS_PERSIST_LOG_LEVEL_ERROR

/*
 * 配置日志功能是否启用
 * 设为1: 启用日志功能
 * 设为0: 禁用所有日志输出, 此时所有日志宏均被定义为空操作, 不产生任何代码
 */
#define SETTINGS_PERSIST_LOG_ENABLED 1

/*
 * 默认模块标签
 * 使用完整文件名作为默认标签, 也可在包含本头文件前通过#define SETTINGS_PERSIST_MODULE_TAG自定义
 * 注意: 必须在每个.c文件中单独定义, 且定义必须出现在#include "settings_persist_log.h"之前
 */
#ifndef SETTINGS_PERSIST_MODULE_TAG
#define SETTINGS_PERSIST_MODULE_TAG __FILE__
#endif

/*
 * 函数级标签管理宏
 * 用于在函数内部设置当前函数的日志标签, 便于跟踪函数调用流程
 * 建议在函数开始处立即调用SETTINGS_PERSIST_SET_FUNC_LOG_TAG
 *
 * 使用示例:
 * void user_function() {
 *     SETTINGS_PERSIST_SET_FUNC_LOG_TAG("MyFunction");
 *     // user code begin here
 * }
 */
#if SETTINGS_PERSIST_LOG_ENABLED
#define SETTINGS_PERSIST_SET_FUNC_LOG_TAG(func_tag)                                                \
    const char *__log_current_func_tag = func_tag;                                                 \
    (void)(__log_current_func_tag)
#else
#define SETTINGS_PERSIST_SET_FUNC_LOG_TAG(func_tag)                                                \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#endif

/*
 * 标准日志打印宏 - 带完整前缀信息
 * 格式: [日志级别][模块标签][函数标签] 消息内容
 * 适用于需要明确来源和上下文的日志记录
 */
#if SETTINGS_PERSIST_LOG_ENABLED
#if SETTINGS_PERSIST_CURRENT_LOG_LEVEL <= SETTINGS_PERSIST_LOG_LEVEL_DEBUG
#define SETTINGS_PERSIST_LOG_DEBUG(format, ...)                                                    \
    do                                                                                             \
    {                                                                                              \
        printf("[SETTINGS_PERSIST][D][%s][%s] " format "\n", SETTINGS_PERSIST_MODULE_TAG,           \
               __log_current_func_tag, ##__VA_ARGS__);                                             \
    } while (0)
#else
#define SETTINGS_PERSIST_LOG_DEBUG(format, ...)                                                    \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#endif

#if SETTINGS_PERSIST_CURRENT_LOG_LEVEL <= SETTINGS_PERSIST_LOG_LEVEL_INFO
#define SETTINGS_PERSIST_LOG_INFO(format, ...)                                                     \
    do                                                                                             \
    {                                                                                              \
        printf("[SETTINGS_PERSIST][I][%s][%s] " format "\n", SETTINGS_PERSIST_MODULE_TAG,           \
               __log_current_func_tag, ##__VA_ARGS__);                                             \
    } while (0)
#else
#define SETTINGS_PERSIST_LOG_INFO(format, ...)                                                     \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#endif

#if SETTINGS_PERSIST_CURRENT_LOG_LEVEL <= SETTINGS_PERSIST_LOG_LEVEL_WARN
#define SETTINGS_PERSIST_LOG_WARN(format, ...)                                                     \
    do                                                                                             \
    {                                                                                              \
        printf("[SETTINGS_PERSIST][W][%s][%s] " format "\n", SETTINGS_PERSIST_MODULE_TAG,           \
               __log_current_func_tag, ##__VA_ARGS__);                                             \
    } while (0)
#else
#define SETTINGS_PERSIST_LOG_WARN(format, ...)                                                     \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#endif

#if SETTINGS_PERSIST_CURRENT_LOG_LEVEL <= SETTINGS_PERSIST_LOG_LEVEL_ERROR
#define SETTINGS_PERSIST_LOG_ERROR(format, ...)                                                    \
    do                                                                                             \
    {                                                                                              \
        printf("\n[SETTINGS_PERSIST][E][%s][%s] " format "\n\n", SETTINGS_PERSIST_MODULE_TAG,       \
               __log_current_func_tag, ##__VA_ARGS__);                                             \
    } while (0)
#else
#define SETTINGS_PERSIST_LOG_ERROR(format, ...)                                                    \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#endif

/*
 * 普通日志打印宏 - 仅输出消息内容
 * 适用于需要保持输出格式简洁的场景, 如协议数据透传、进度显示等
 * 注意: 普通日志不包含日志级别、模块标签等信息, 无法直接定位来源
 */
#if SETTINGS_PERSIST_CURRENT_LOG_LEVEL <= SETTINGS_PERSIST_LOG_LEVEL_DEBUG
#define SETTINGS_PERSIST_LOG_DEBUG_NORMAL(format, ...)                                             \
    do                                                                                             \
    {                                                                                              \
        printf(format, ##__VA_ARGS__);                                                             \
    } while (0)
#else
#define SETTINGS_PERSIST_LOG_DEBUG_NORMAL(format, ...)                                             \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#endif

#if SETTINGS_PERSIST_CURRENT_LOG_LEVEL <= SETTINGS_PERSIST_LOG_LEVEL_INFO
#define SETTINGS_PERSIST_LOG_INFO_NORMAL(format, ...)                                              \
    do                                                                                             \
    {                                                                                              \
        printf(format, ##__VA_ARGS__);                                                             \
    } while (0)
#else
#define SETTINGS_PERSIST_LOG_INFO_NORMAL(format, ...)                                              \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#endif

#if SETTINGS_PERSIST_CURRENT_LOG_LEVEL <= SETTINGS_PERSIST_LOG_LEVEL_WARN
#define SETTINGS_PERSIST_LOG_WARN_NORMAL(format, ...)                                              \
    do                                                                                             \
    {                                                                                              \
        printf(format, ##__VA_ARGS__);                                                             \
    } while (0)
#else
#define SETTINGS_PERSIST_LOG_WARN_NORMAL(format, ...)                                              \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#endif

#if SETTINGS_PERSIST_CURRENT_LOG_LEVEL <= SETTINGS_PERSIST_LOG_LEVEL_ERROR
#define SETTINGS_PERSIST_LOG_ERROR_NORMAL(format, ...)                                             \
    do                                                                                             \
    {                                                                                              \
        printf(format, ##__VA_ARGS__);                                                             \
    } while (0)
#else
#define SETTINGS_PERSIST_LOG_ERROR_NORMAL(format, ...)                                             \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#endif
#else
/* 日志禁用时, 所有日志宏均定义为空操作, 不产生任何代码 */
#define SETTINGS_PERSIST_LOG_DEBUG(format, ...)                                                    \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#define SETTINGS_PERSIST_LOG_INFO(format, ...)                                                     \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#define SETTINGS_PERSIST_LOG_WARN(format, ...)                                                     \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#define SETTINGS_PERSIST_LOG_ERROR(format, ...)                                                    \
    do                                                                                             \
    {                                                                                              \
    } while (0)

#define SETTINGS_PERSIST_LOG_DEBUG_NORMAL(format, ...)                                             \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#define SETTINGS_PERSIST_LOG_INFO_NORMAL(format, ...)                                              \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#define SETTINGS_PERSIST_LOG_WARN_NORMAL(format, ...)                                              \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#define SETTINGS_PERSIST_LOG_ERROR_NORMAL(format, ...)                                             \
    do                                                                                             \
    {                                                                                              \
    } while (0)
#endif

#endif /* _SETTINGS_PERSIST_LOG_H */