cmake_minimum_required(VERSION 3.8)

# 设置库名称
set(LIB_NAME settings_persist)

# 定义源文件列表（只包含源文件，不包含头文件）
set(LIB_SOURCES
    "inih-57/ini.c"
    "settings_auto_generated.c"
    "settings_persist.c"
)

# 先创建目标（必须在target_*命令之前）
add_library(${LIB_NAME} STATIC ${LIB_SOURCES})

# 设置C标准
set_property(TARGET ${LIB_NAME} PROPERTY C_STANDARD 11)
set_property(TARGET ${LIB_NAME} PROPERTY C_STANDARD_REQUIRED ON)

# 添加头文件搜索路径（当前目录的头文件，对外部可见）
target_include_directories(${LIB_NAME} PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
)

if(SIMULATOR)
    message(STATUS "正在编译settings_persist: 此次编译为仿真UI")
    # 目标级宏定义
    target_compile_definitions(${LIB_NAME} PRIVATE
        SIMULATOR=1
    )
else()
    message(STATUS "正在编译settings_persist: 此次编译为交叉编译")
endif()

# 链接编译的依赖库
target_link_libraries(${LIB_NAME} PRIVATE
    pthread
)

# 设置编译选项
target_compile_options(${LIB_NAME} PRIVATE
    -Wall                   # 开启所有警告
    -Wextra                 # 开启额外警告
    -Werror                 # 将警告视为错误
    -O2                     # 优化级别2
    $<$<CONFIG:Debug>:-g>   # 调试模式添加调试信息
)