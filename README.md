## settings_persist 模块使用说明文档

### 1. 模块概述

`settings_persist` 是一个基于 INI 配置文件的数据持久化模块，具备以下核心特性：

- **自动代码生成**：通过 Python 脚本根据 INI 配置模板自动生成 C 语言代码
- **数据持久化**：将程序运行时的设置数据持久化保存到文件系统
- **数据校验**：采用 CRC-16/IBM 校验算法保证数据完整性
- **容错机制**：支持主备文件双备份，提高数据安全性
- **延迟写入**：减少频繁写入对存储设备的影响
- **线程安全**：多线程环境下安全地访问和修改配置数据

### 2. 自动生成代码机制

#### 2.1 INI 配置模板

代码生成的核心是位于 `code_generator/settings(for_code_generator).ini` 的配置文件，其格式要求非常严格：

```ini
[section_name]
; key_name: type=data_type, default=default_value, min=min_value, max=max_value
key_name = default_value

[AnotherSection]
; another_key: type=string:length, default=default_string
another_key = default_string
```

支持的数据类型包括：
- `int`: 整数类型，需指定 `min` 和 `max`
- `bool`: 布尔类型
- `string:length`: 字符串类型，需指定最大长度

#### 2.2 生成的代码文件

运行 [generate_settings_from_ini.py](.\settings_persist\code_generator\generate_settings_from_ini.py) 脚本后会生成两个文件：

1. [settings_persist.h](.\settings_persist\settings_persist.h)：包含配置结构体定义和函数声明
2. [settings_auto_generated.c](.\settings_persist\settings_auto_generated.c)：包含具体实现代码

### 3. 主要功能和使用方法

#### 3.1 初始化模块

```c
int settings_persist_init(void);
```

在使用模块前必须调用此函数进行初始化，它会：
- 加载配置文件（优先使用主文件，失败则尝试备份文件）
- 启动后台持久化线程

#### 3.2 获取配置数据

```c
int settings_persist_get_data(Settings *settings);
```

获取当前的配置数据副本。

#### 3.3 更新配置数据

有两种方式更新配置：

1. **整体更新**：
   ```c
   int settings_persist_set_data(const Settings *settings);
   ```

2. **单项更新**（推荐）：
   ```c
   // 例如更新音频音量
   int settings_persist_set_Audio_volume(int volume);
   
   // 更新显示亮度
   int settings_persist_set_Display_brightness(int brightness);
   ```

这些的配置更新接口都带有输入参数校验功能（有效范围来自于`code_generator/settings(for_code_generator).ini`）。

#### 3.4 重置配置

```c
int settings_persist_reset_all_data(void);
```

将所有配置重置为默认值（默认值也来自于`code_generator/settings(for_code_generator).ini`）。

#### 3.5 销毁模块

```c
int settings_persist_deinit(void);
```

停止并清理模块资源。

### 4. 配置文件管理

模块使用以下文件路径存储配置：

**实际设备模式**：
- 主配置文件：`/userdata/settings.ini`
- 备份文件：`/userdata/settings.bak`
- 临时文件：`/userdata/settings.tmp` 和 `/userdata/settings_bak.tmp`

**模拟器模式**：
- 主配置文件：`./settings(for_ui_simulator).ini`
- 备份文件：`./settings(for_ui_simulator).bak`
- 临时文件：`./settings(for_ui_simulator).tmp` 和 `./settings_bak(for_ui_simulator).tmp`

### 5. 使用流程示例

```c
// 1. 初始化模块
if (settings_persist_init() != 0) {
    printf("Failed to initialize settings persist module\n");
    return -1;
}

// 2. 获取当前配置
Settings current_settings;
settings_persist_get_data(&current_settings);

// 3. 修改特定配置项
settings_persist_set_Audio_volume(80);
settings_persist_set_Display_brightness(70);

// 4. 程序退出前销毁模块
settings_persist_deinit();
```

### 6. 注意事项

1. **线程安全**：所有接口都是线程安全的，可以在多线程环境中使用
2. **延迟写入**：配置变更不会立即写入文件，而是延迟一定时间后批量写入
3. **数据校验**：每次读取都会进行 CRC 校验，确保数据完整性
4. **自动恢复**：当配置文件损坏时，会自动使用备份文件或恢复默认值
5. **避免重复初始化**：不要多次调用 [settings_persist_init()](.\settings_persist.h#L42-L42) 函数

### 7. 扩展配置

如需添加新的配置项，只需修改 [settings(for_code_generator).ini](.\settings_persist\code_generator\settings(for_code_generator).ini) 文件，然后重新运行 [generate_settings_from_ini.py](.\settings_persist\code_generator\generate_settings_from_ini.py) 脚本即可自动生成相应的代码。
