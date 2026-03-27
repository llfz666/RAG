# C++ 后端开发知识域详细地图

本文档提供 12 个知识域、55 个知识点的详细学习内容，包括核心概念、面试常见问题、代码示例和推荐资源。

---

## D1 C++ 语言基础

### D1.1 编译模型与链接

**核心概念**:
- **编译单元**: 每个 `.cpp` 文件独立编译成目标文件 (`.o`/`.obj`)
- **链接过程**: 链接器合并目标文件，解析符号引用
- **符号解析**: 函数/变量名的 name mangling，extern "C" 禁用 mangling
- **ODR (One Definition Rule)**: 程序中每个定义只能有一个

**面试问题**:
1. 描述 C++ 从源代码到可执行文件的完整过程
2. 头文件重复包含会导致什么问题？如何解决？
3. 什么是 ODR？违反 ODR 会发生什么？
4. extern "C" 的作用是什么？使用场景？

**代码示例**:
```cpp
// header.h - 错误示例
int global_var = 42;  // 每个包含此头文件的 cpp 都会定义这个变量

// header.h - 正确做法
extern int global_var;  // 声明

// global.cpp
int global_var = 42;  // 定义

// main.cpp
extern int global_var;  // 使用
```

---

### D1.2 类型系统与转换

**核心概念**:
- **基本类型**: 整型、浮点型、布尔型、void
- **类型转换**:
  - `static_cast<T>(expr)`: 相关类型间的转换
  - `dynamic_cast<T>(expr)`: 运行时类型检查，用于多态
  - `const_cast<T>(expr)`: 添加/移除 const
  - `reinterpret_cast<T>(expr)`: 低级别重新解释
- **类型推导**: `auto`、`decltype`

**面试问题**:
1. 四种类型转换的区别和使用场景
2. auto 推导规则是什么？什么时候不能用 auto？
3. decltype 和 auto 的区别？

---

### D1.3 作用域与生命周期

**核心概念**:
- **命名空间**: 避免命名冲突，组织代码
- **类作用域**: 成员访问控制
- **存储期**:
  - 静态存储期：全局变量、static 变量
  - 线程存储期：thread_local 变量
  - 自动存储期：局部变量
  - 动态存储期：new 分配的对象

---

### D1.4 const 正确性

**核心概念**:
- **const 语义**: 表示不可修改的承诺
- **mutable**: 允许在 const 成员函数中修改成员
- **constexpr**: 编译期常量，函数可在编译期求值

**面试问题**:
1. const 成员函数能修改哪些成员？
2. constexpr 和 const 的区别？
3. 什么是 const 正确性？为什么重要？

---

### D1.5 值类别与移动语义

**核心概念**:
- **lvalue**: 有身份的对象，可取地址
- **rvalue**: 临时对象，无身份
- **xvalue**: 即将被移动的对象
- **std::move**: 转换为右值引用
- **std::forward**: 完美转发
- **引用折叠**: `T&& &` → `T&`, `T&& &&` → `T&&`

**代码示例**:
```cpp
// 移动构造函数示例
class MyString {
    char* data_;
    size_t size_;
public:
    // 移动构造函数
    MyString(MyString&& other) noexcept 
        : data_(other.data_), size_(other.size_) {
        other.data_ = nullptr;  // 置空，防止析构释放
        other.size_ = 0;
    }
    
    // 移动赋值运算符
    MyString& operator=(MyString&& other) noexcept {
        if (this != &other) {
            delete[] data_;
            data_ = other.data_;
            size_ = other.size_;
            other.data_ = nullptr;
            other.size_ = 0;
        }
        return *this;
    }
};
```

---

## D2 内存管理

### D2.1 栈与堆

**核心概念**:
- **栈内存**: 自动管理，速度快，大小有限
- **堆内存**: 手动管理 (new/delete)，灵活，可能碎片化
- **内存对齐**: `alignof`, `alignas`
- **placement new**: 在预分配内存上构造对象

---

### D2.2 RAII 原则

**核心概念**:
- **Resource Acquisition Is Initialization**: 资源获取即初始化
- **异常安全**: RAII 保证资源在异常时也能释放
- **RAII 包装器**: lock_guard、unique_ptr、scope_guard

**代码示例**:
```cpp
// 自定义 RAII 文件句柄
class FileHandle {
    FILE* file_;
public:
    explicit FileHandle(const char* path, const char* mode) 
        : file_(std::fopen(path, mode)) {
        if (!file_) throw std::runtime_error("Failed to open file");
    }
    
    ~FileHandle() {
        if (file_) std::fclose(file_);
    }
    
    // 禁止拷贝
    FileHandle(const FileHandle&) = delete;
    FileHandle& operator=(const FileHandle&) = delete;
    
    // 允许移动
    FileHandle(FileHandle&& other) noexcept : file_(other.file_) {
        other.file_ = nullptr;
    }
    
    FILE* get() const { return file_; }
};

// 使用
void processFile() {
    FileHandle fh("data.txt", "r");  // 自动关闭
    // ... 使用 fh.get()
}  // 离开作用域自动 fclose
```

---

### D2.3 智能指针

**核心概念**:
- **unique_ptr**: 独占所有权，不可拷贝，可移动
- **shared_ptr**: 共享所有权，引用计数
- **weak_ptr**: 弱引用，解决循环引用
- **自定义删除器**: 用于特殊资源释放

**代码示例**:
```cpp
// 循环引用问题
struct B;

struct A {
    std::shared_ptr<B> b;
    ~A() { std::cout << "A destroyed\n"; }
};

struct B {
    std::shared_ptr<A> a;  // 问题：应该用 weak_ptr
    ~B() { std::cout << "B destroyed\n"; }
};

// 正确做法
struct B {
    std::weak_ptr<A> a;  // 弱引用，不增加引用计数
};
```

---

### D2.4 内存模型

**核心概念**:
- **happens-before**: 操作 A 在操作 B 之前发生
- **内存序**:
  - `memory_order_relaxed`: 无顺序保证
  - `memory_order_acquire`: 获取操作
  - `memory_order_release`: 释放操作
  - `memory_order_acq_rel`: 获取 + 释放
  - `memory_order_seq_cst`: 顺序一致 (默认)

---

### D2.5 自定义分配器

**核心概念**:
- **allocator 接口**: allocate, deallocate, construct, destroy
- **内存池**: 预分配大块内存，按需分配
- **对象池**: 复用已分配对象

---

## D3 面向对象设计

### D3.1 继承体系

**核心概念**:
- **访问控制**: public/protected/private 继承
- **多重继承**: 菱形继承问题
- **虚继承**: 解决菱形继承的重复基类问题

---

### D3.2 多态与虚函数

**核心概念**:
- **虚函数表 (vtable)**: 存储虚函数指针的表
- **动态绑定**: 运行时根据实际类型调用虚函数
- **override/final**: 显式说明意图，编译器检查

**代码示例**:
```cpp
class Shape {
public:
    virtual double area() const = 0;  // 纯虚函数
    virtual ~Shape() = default;  // 虚析构函数
};

class Rectangle : public Shape {
    double width_, height_;
public:
    Rectangle(double w, double h) : width_(w), height_(h) {}
    double area() const override { return width_ * height_; }
};
```

---

### D3.3 拷贝控制

**核心概念**:
- **五法则**: 析构、拷贝构造、拷贝赋值、移动构造、移动赋值
- ** Rule of Zero**: 能用成员默认行为就不要自定义
- ** Rule of Five**: 自定义其一，通常都需要自定义

---

### D3.4 设计原则

**核心概念**:
- **SOLID**:
  - S: Single Responsibility 单一职责
  - O: Open/Closed 开闭原则
  - L: Liskov 替换
  - I: Interface Segregation 接口隔离
  - D: Dependency Inversion 依赖倒置

---

## D4 模板与泛型编程

### D4.1 函数/类模板

**核心概念**:
- **模板参数**: 类型参数、非类型参数、模板模板参数
- **特化**: 全特化、偏特化
- **隐式实例化**: 编译器根据使用推导类型

---

### D4.2 变长模板

**核心概念**:
- **参数包**: `typename... Args`
- **折叠表达式 (C++17)**: `(args + ... + 0)`
- **递归展开**: 传统展开方式

**代码示例**:
```cpp
// 折叠表达式 (C++17)
template<typename... Args>
auto sum(Args... args) {
    return (args + ... + 0);  // 右折叠
}

// 递归展开 (C++11/14)
template<typename T>
T sum(T t) { return t; }

template<typename T, typename... Args>
T sum(T first, Args... rest) {
    return first + sum(rest...);
}
```

---

### D4.3 SFINAE 与 enable_if

**核心概念**:
- **SFINAE**: Substitution Failure Is Not An Error
- **enable_if**: 条件启用模板
- **类型特征**: `<type_traits>` 中的工具

**代码示例**:
```cpp
// 只接受整数类型
template<typename T>
typename std::enable_if<std::is_integral<T>::value, T>::type
add(T a, T b) {
    return a + b;
}

// C++17 简化写法
template<typename T>
std::enable_if_t<std::is_integral_v<T>, T>
add(T a, T b) { return a + b; }
```

---

### D4.4 CRTP 模式

**核心概念**:
- **奇异递归模板模式**: 派生类作为模板参数传给基类
- **静态多态**: 编译期绑定，无虚函数开销

**代码示例**:
```cpp
template<typename Derived>
class Comparable {
public:
    bool operator<(const Comparable& other) const {
        const Derived& self = static_cast<const Derived&>(*this);
        const Derived& o = static_cast<const Derived&>(other);
        return self.compare(o) < 0;
    }
};

class MyInt : public Comparable<MyInt> {
    int value_;
public:
    MyInt(int v) : value_(v) {}
    int compare(const MyInt& o) const { return value_ - o.value_; }
};
```

---

### D4.5 C++20 Concepts

**核心概念**:
- **概念定义**: `concept ConceptName = 约束表达式`
- **requires 子句**: 添加约束
- **概念库**: `<concepts>` 中的预定义概念

**代码示例**:
```cpp
template<typename T>
concept Addable = requires(T a, T b) {
    { a + b } -> std::same_as<T>;
};

template<Addable T>
T add(T a, T b) { return a + b; }

// 或使用 requires 子句
template<typename T>
requires Addable<T>
T add(T a, T b) { return a + b; }
```

---

## D5 STL 标准库

### D5.1 序列容器

**核心概念**:
- **vector**: 动态数组，随机访问 O(1)，尾部插入 O(1)
- **deque**: 双端队列，两端插入 O(1)
- **list**: 双向链表，任意位置插入 O(1)
- **forward_list**: 单向链表
- **array**: 固定大小数组

---

### D5.2 关联容器

**核心概念**:
- **set/map**: 红黑树实现，有序，查找 O(log n)
- **unordered_set/unordered_map**: 哈希表实现，无序，查找 O(1) 平均

---

### D5.3 迭代器与范围

**核心概念**:
- **迭代器类别**: 输入、输出、前向、双向、随机访问
- **迭代器失效**: 容器修改后迭代器可能失效
- **范围库 (C++20)**: views、adaptors

---

### D5.4 算法库

**核心概念**:
- **常用算法**: sort, find, transform, copy, accumulate
- **执行策略 (C++17)**: seq, par, par_unseq
- **算法复杂度**: 理解各算法的时间复杂度

---

### D5.5 函数对象与 lambda

**核心概念**:
- **std::function**: 类型擦除的函数包装器
- **std::bind**: 绑定参数
- **lambda**: 匿名函数，捕获列表

**代码示例**:
```cpp
// lambda 捕获
int factor = 2;
auto multiply = [factor](int x) { return x * factor; };  // 值捕获
auto multiplyRef = [&factor](int x) { return x * factor; };  // 引用捕获

// 通用 lambda (C++14)
auto add = [](auto a, auto b) { return a + b; };

// 捕获 this
class Handler {
    int value_ = 42;
public:
    auto getCallback() {
        return [this]() { return value_; };  // 捕获 this
    }
};
```

---

## D6 并发编程

### D6.1 线程基础

**核心概念**:
- **std::thread**: 创建和管理线程
- **线程生命周期**: 创建、运行、join/detach
- **线程局部存储**: `thread_local`

**代码示例**:
```cpp
#include <thread>
#include <vector>

void worker(int id) {
    std::cout << "Worker " << id << " running\n";
}

int main() {
    std::vector<std::thread> threads;
    for (int i = 0; i < 4; ++i) {
        threads.emplace_back(worker, i);
    }
    for (auto& t : threads) {
        t.join();  // 等待所有线程完成
    }
}
```

---

### D6.2 互斥与锁

**核心概念**:
- **mutex**: 互斥锁
- **recursive_mutex**: 可重入锁
- **shared_mutex**: 读写锁 (C++17)
- **lock_guard**: 作用域锁 (RAII)
- **unique_lock**: 可延迟锁定的锁

---

### D6.3 条件变量与信号量

**核心概念**:
- **condition_variable**: wait/notify
- **生产者消费者模式**: 经典并发模式
- **C++20 semaphore**: 计数信号量

**代码示例**:
```cpp
#include <queue>
#include <mutex>
#include <condition_variable>

template<typename T>
class ThreadSafeQueue {
    std::queue<T> queue_;
    mutable std::mutex mutex_;
    std::condition_variable cond_;
    
public:
    void push(T value) {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            queue_.push(std::move(value));
        }
        cond_.notify_one();
    }
    
    T pop() {
        std::unique_lock<std::mutex> lock(mutex_);
        cond_.wait(lock, [this] { return !queue_.empty(); });
        T value = std::move(queue_.front());
        queue_.pop();
        return value;
    }
};
```

---

### D6.4 原子操作

**核心概念**:
- **std::atomic**: 原子类型
- **CAS (Compare-And-Swap)**: 无锁编程基础
- **memory_order**: 内存顺序控制

---

### D6.5 并发数据结构

**核心概念**:
- **线程安全队列**: 加锁队列
- **读写锁**: 多读单写
- **自旋锁**: 忙等待锁
- **无锁栈**: 基于原子的无锁实现

---

## D7 网络编程基础

### D7.1 Socket 编程

**核心概念**:
- **TCP Socket**: 流式 Socket
- **UDP Socket**: 数据报 Socket
- **地址结构**: sockaddr_in, sockaddr_in6
- **字节序**: htonl, ntohl, htons, ntohs

---

### D7.2 TCP/IP 协议

**核心概念**:
- **三次握手**: SYN → SYN-ACK → ACK
- **四次挥手**: FIN → ACK, FIN → ACK
- **拥塞控制**: 慢启动、拥塞避免、快速重传
- **粘包处理**: 长度前缀、分隔符、固定长度

---

### D7.3 IO 多路复用

**核心概念**:
- **select**: 跨平台，FD_SETSIZE 限制
- **poll**: 无 FD 数量限制
- **epoll**: Linux 高效 IO 多路复用
- **IOCP**: Windows 完成端口
- **Reactor/Proactor**: 事件驱动模式

---

### D7.4 异步 IO

**核心概念**:
- **std::async**: 异步任务
- **future/promise**: 异步结果
- **C++20 coroutine**: 协程基础

---

## D8 数据库与 ORM

### D8.1 SQL 基础

**核心概念**:
- **CRUD**: Create, Read, Update, Delete
- **索引原理**: B+ 树、哈希索引
- **事务隔离级别**: Read Uncommitted/Committed/Repeatable Read/Serializable
- **SQL 注入防护**: 参数化查询

---

### D8.2 连接池设计

**核心概念**:
- **连接复用**: 减少连接创建开销
- **超时控制**: 获取超时、空闲超时
- **健康检查**: 定期验证连接有效性

---

### D8.3 ORM 设计

**核心概念**:
- **对象关系映射**: 类→表，对象→行
- **延迟加载**: 按需加载关联数据
- **N+1 问题**: 避免循环查询

---

### D8.4 Redis 缓存

**核心概念**:
- **数据结构**: string, hash, list, set, zset
- **持久化**: RDB 快照、AOF 日志
- **缓存问题**: 穿透、雪崩、击穿

---

## D9 系统设计与架构

### D9.1 分层架构

**核心概念**:
- **表现层**: UI、API 接口
- **业务层**: 业务逻辑
- **数据层**: 数据访问
- **依赖方向**: 上层依赖下层

---

### D9.2 模块化设计

**核心概念**:
- **高内聚**: 模块内部紧密相关
- **低耦合**: 模块间依赖最小化
- **接口隔离**: 小接口优于大接口

---

### D9.3 依赖注入

**核心概念**:
- **IoC 容器**: 控制反转
- **工厂模式**: 对象创建抽象
- **服务定位器**: 服务注册与查找

---

### D9.4 配置管理

**核心概念**:
- **配置加载**: YAML、JSON、XML
- **热更新**: 运行时重新加载配置
- **多环境**: dev/test/prod 环境隔离

---

### D9.5 日志系统

**核心概念**:
- **日志级别**: DEBUG、INFO、WARNING、ERROR、CRITICAL
- **异步日志**: 不阻塞主线程
- **日志轮转**: 按大小/时间分割
- **结构化日志**: JSON 格式日志

---

## D10 性能优化

### D10.1 性能分析

**核心概念**:
- **profiler 工具**: perf、VTune、gprof
- **火焰图**: 可视化 CPU 热点
- **瓶颈识别**: CPU bound vs IO bound

---

### D10.2 缓存优化

**核心概念**:
- **CPU 缓存**: L1、L2、L3
- **缓存行**: 通常 64 字节
- **数据局部性**: 时间局部性、空间局部性
- **缓存友好设计**: 连续内存、顺序访问

---

### D10.3 零拷贝技术

**核心概念**:
- **mmap**: 内存映射文件
- **sendfile**: 内核空间数据传输
- **DMA**: 直接内存访问

---

### D10.4 内存池优化

**核心概念**:
- **对象复用**: 避免频繁分配释放
- **减少碎片**: 固定大小块分配
- **预分配**: 提前分配所需内存

---

### D10.5 SIMD 与向量化

**核心概念**:
- **SSE/AVX**: x86 SIMD 指令集
- **自动向量化**: 编译器优化
- **数据并行**: 同时处理多个数据

---

## D11 调试与测试

### D11.1 调试技巧

**核心概念**:
- **gdb/lldb**: 命令行调试器
- **core dump 分析**: 崩溃后分析
- **内存泄漏检测**: valgrind、AddressSanitizer

---

### D11.2 单元测试

**核心概念**:
- **GoogleTest**: 主流 C++ 测试框架
- **测试用例设计**: 边界值、等价类
- **Mock 框架**: GoogleMock
- **测试覆盖率**: gcov、lcov

---

### D11.3 集成测试

**核心概念**:
- **端到端测试**: 完整流程测试
- **契约测试**: 接口契约验证
- **性能测试**: 压测、基准测试

---

### D11.4 持续集成

**核心概念**:
- **CI/CD 流程**: 自动化构建、测试、部署
- **质量门禁**: 覆盖率、静态分析
- **代码审查**: PR/MR 流程

---

## D12 工程化实践

### D12.1 CMake 构建

**核心概念**:
- **CMakeLists.txt**: 构建配置
- **目标管理**: add_executable, add_library
- **依赖管理**: find_package, FetchContent
- **跨平台构建**: Windows/Linux/macOS

**代码示例**:
```cmake
cmake_minimum_required(VERSION 3.16)
project(MyProject VERSION 1.0.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 添加可执行文件
add_executable(my_app src/main.cpp src/app.cpp)

# 添加库
add_library(my_lib STATIC src/lib.cpp)
target_include_directories(my_lib PUBLIC include/)

# 链接依赖
target_link_libraries(my_app PRIVATE my_lib)

# 测试
enable_testing()
add_subdirectory(tests)
```

---

### D12.2 代码规范

**核心概念**:
- **Google C++ Style**: 广泛采用的规范
- **命名规范**: 驼峰、下划线
- **注释规范**: 文档注释、实现注释
- **代码格式化**: clang-format

---

### D12.3 版本控制

**核心概念**:
- **Git 工作流**: Feature branch、GitFlow
- **分支策略**: main/develop/feature/hotfix
- **代码审查**: PR/MR 流程
- **版本发布**: Semantic Versioning

---

### D12.4 包管理

**核心概念**:
- **Conan**: C/C++ 包管理器
- **vcpkg**: Microsoft 包管理器
- **依赖锁定**: 锁定依赖版本
- **二进制缓存**: 加速构建

---

## 学习建议

1. **循序渐进**: 从 D1 基础开始，逐步深入
2. **理论结合实践**: 每个知识点都要写代码验证
3. **刻意练习**: 针对薄弱环节重点突破
4. **总结归纳**: 学完每个知识域后做总结
5. **模拟面试**: 用自己的话解释概念

---

*本文档为 cpp-backend-learner skill 的配套参考资料*