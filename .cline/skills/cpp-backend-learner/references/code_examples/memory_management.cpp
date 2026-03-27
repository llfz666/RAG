/**
 * @file memory_management.cpp
 * @brief C++ 内存管理核心示例代码
 * 
 * 涵盖：栈/堆、RAII、智能指针、移动语义
 */

#include <iostream>
#include <memory>
#include <vector>
#include <string>
#include <cstring>

// ============================================================================
// 1. 栈与堆对比示例
// ============================================================================

void stack_vs_heap() {
    // 栈分配 - 自动管理，速度快
    int stack_var = 42;
    std::string stack_str = "Hello";  // string 对象在栈上，内容在堆上
    
    // 堆分配 - 手动管理，灵活
    int* heap_var = new int(42);
    delete heap_var;  // 必须手动释放
    
    // 现代 C++ 推荐：使用智能指针
    auto smart_ptr = std::make_unique<int>(42);  // 自动释放
}

// ============================================================================
// 2. RAII 示例 - 文件句柄包装器
// ============================================================================

class FileHandle {
    FILE* file_;
    
public:
    // 构造函数 - 资源获取
    explicit FileHandle(const char* path, const char* mode) 
        : file_(std::fopen(path, mode)) {
        if (!file_) {
            throw std::runtime_error("Failed to open file: " + std::string(path));
        }
        std::cout << "File opened: " << path << "\n";
    }
    
    // 析构函数 - 资源释放
    ~FileHandle() {
        if (file_) {
            std::fclose(file_);
            std::cout << "File closed\n";
        }
    }
    
    // 禁止拷贝 - 防止双重释放
    FileHandle(const FileHandle&) = delete;
    FileHandle& operator=(const FileHandle&) = delete;
    
    // 允许移动
    FileHandle(FileHandle&& other) noexcept : file_(other.file_) {
        other.file_ = nullptr;
    }
    
    FileHandle& operator=(FileHandle&& other) noexcept {
        if (this != &other) {
            if (file_) std::fclose(file_);
            file_ = other.file_;
            other.file_ = nullptr;
        }
        return *this;
    }
    
    // 获取底层文件指针
    FILE* get() const { return file_; }
    
    // 写入数据
    void write(const std::string& data) {
        if (file_) {
            std::fputs(data.c_str(), file_);
        }
    }
};

void raii_example() {
    try {
        FileHandle fh("test.txt", "w");
        fh.write("Hello, RAII!");
        // 离开作用域自动关闭文件，无需显式调用 fclose
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
    }
}

// ============================================================================
// 3. 智能指针示例
// ============================================================================

void unique_ptr_example() {
    // unique_ptr - 独占所有权
    std::unique_ptr<int> ptr1 = std::make_unique<int>(42);
    // std::unique_ptr<int> ptr2 = ptr1;  // 错误！不能拷贝
    std::unique_ptr<int> ptr3 = std::move(ptr1);  // 可以移动
    // ptr1 现在为空，ptr3 拥有资源
    
    // 自定义删除器
    auto deleter = [](int* p) {
        std::cout << "Deleting with custom deleter\n";
        delete p;
    };
    std::unique_ptr<int, decltype(deleter)> ptr4(new int(42), deleter);
}

void shared_ptr_example() {
    // shared_ptr - 共享所有权
    std::shared_ptr<int> ptr1 = std::make_shared<int>(42);
    std::shared_ptr<int> ptr2 = ptr1;  // 引用计数 +1
    std::shared_ptr<int> ptr3 = ptr1;  // 引用计数再 +1
    
    std::cout << "Use count: " << ptr1.use_count() << "\n";  // 输出 3
    
    // weak_ptr - 不增加引用计数
    std::weak_ptr<int> weak = ptr1;
    std::cout << "Weak use count: " << weak.use_count() << "\n";
    
    // 提升为 shared_ptr
    if (auto shared = weak.lock()) {
        std::cout << "Value: " << *shared << "\n";
    }
}

// 循环引用问题与解决
struct B;  // 前向声明

struct A {
    std::shared_ptr<B> b;  // A 持有 B
    ~A() { std::cout << "A destroyed\n"; }
};

struct B {
    std::weak_ptr<A> a;  // B 用 weak_ptr 持有 A，避免循环引用
    ~B() { std::cout << "B destroyed\n"; }
};

void circular_reference_demo() {
    auto a = std::make_shared<A>();
    auto b = std::make_shared<B>();
    
    a->b = b;      // A -> B
    b->a = a;      // B -/> A (weak, 不增加引用计数)
    
    // 离开作用域时，a 和 b 都能正确释放
}

// ============================================================================
// 4. 移动语义示例
// ============================================================================

class MyString {
    char* data_;
    size_t size_;
    
public:
    // 默认构造函数
    MyString() : data_(nullptr), size_(0) {}
    
    // 构造函数
    MyString(const char* str) : size_(std::strlen(str)) {
        data_ = new char[size_ + 1];
        std::strcpy(data_, str);
        std::cout << "Constructor called\n";
    }
    
    // 拷贝构造函数
    MyString(const MyString& other) : size_(other.size_) {
        data_ = new char[size_ + 1];
        std::strcpy(data_, other.data_);
        std::cout << "Copy constructor called\n";
    }
    
    // 拷贝赋值运算符
    MyString& operator=(const MyString& other) {
        if (this != &other) {
            delete[] data_;
            size_ = other.size_;
            data_ = new char[size_ + 1];
            std::strcpy(data_, other.data_);
            std::cout << "Copy assignment called\n";
        }
        return *this;
    }
    
    // 移动构造函数 - 关键！
    MyString(MyString&& other) noexcept 
        : data_(other.data_), size_(other.size_) {
        other.data_ = nullptr;  // 置空，防止析构释放
        other.size_ = 0;
        std::cout << "Move constructor called\n";
    }
    
    // 移动赋值运算符 - 关键！
    MyString& operator=(MyString&& other) noexcept {
        if (this != &other) {
            delete[] data_;  // 释放原有资源
            data_ = other.data_;
            size_ = other.size_;
            other.data_ = nullptr;  // 置空
            other.size_ = 0;
            std::cout << "Move assignment called\n";
        }
        return *this;
    }
    
    // 析构函数
    ~MyString() {
        delete[] data_;
    }
    
    // 获取字符串
    const char* c_str() const { return data_ ? data_ : ""; }
};

void move_semantics_demo() {
    MyString s1("Hello");
    
    // 触发拷贝构造
    MyString s2 = s1;
    std::cout << "s2: " << s2.c_str() << "\n";
    
    // 触发移动构造 - 使用 std::move
    MyString s3 = std::move(s1);
    std::cout << "s3: " << s3.c_str() << "\n";
    std::cout << "s1 (moved): " << s1.c_str() << "\n";  // 空字符串
    
    // 返回值优化 (RVO/NRVO)
    auto create_string = []() -> MyString {
        MyString temp("Temporary");
        return temp;  // 编译器会优化为移动
    };
    MyString s4 = create_string();
}

// ============================================================================
// 5. 内存对齐示例
// ============================================================================

struct Unaligned {
    char a;      // 1 byte
    // 3 bytes padding
    double b;    // 8 bytes
    int c;       // 4 bytes
    // 4 bytes padding
};               // Total: 24 bytes

struct Aligned {
    double b;    // 8 bytes (先放大的)
    int c;       // 4 bytes
    char a;      // 1 byte
    // 3 bytes padding
};               // Total: 16 bytes

void alignment_demo() {
    std::cout << "Unaligned size: " << sizeof(Unaligned) << "\n";
    std::cout << "Aligned size: " << sizeof(Aligned) << "\n";
    std::cout << "alignof(double): " << alignof(double) << "\n";
    
    // 使用 alignas 指定对齐
    alignas(32) int aligned_int = 42;
    std::cout << "Aligned int address: " << &aligned_int << "\n";
}

// ============================================================================
// 6. 自定义分配器示例
// ============================================================================

template<typename T>
class SimpleAllocator {
public:
    using value_type = T;
    
    SimpleAllocator() noexcept {
        std::cout << "Allocator created\n";
    }
    
    template<typename U>
    SimpleAllocator(const SimpleAllocator<U>&) noexcept {}
    
    T* allocate(std::size_t n) {
        std::cout << "Allocating " << n << " elements\n";
        return static_cast<T*>(::operator new(n * sizeof(T)));
    }
    
    void deallocate(T* p, std::size_t) noexcept {
        std::cout << "Deallocating\n";
        ::operator delete(p);
    }
};

template<typename T, typename U>
bool operator==(const SimpleAllocator<T>&, const SimpleAllocator<U>&) { 
    return true; 
}

template<typename T, typename U>
bool operator!=(const SimpleAllocator<T>&, const SimpleAllocator<U>&) { 
    return false; 
}

void custom_allocator_demo() {
    std::vector<int, SimpleAllocator<int>> vec;
    vec.push_back(1);
    vec.push_back(2);
    vec.push_back(3);
}

// ============================================================================
// 主函数 - 运行所有示例
// ============================================================================

int main() {
    std::cout << "=== Stack vs Heap ===\n";
    stack_vs_heap();
    
    std::cout << "\n=== RAII Example ===\n";
    raii_example();
    
    std::cout << "\n=== Unique Ptr ===\n";
    unique_ptr_example();
    
    std::cout << "\n=== Shared Ptr ===\n";
    shared_ptr_example();
    
    std::cout << "\n=== Circular Reference ===\n";
    circular_reference_demo();
    
    std::cout << "\n=== Move Semantics ===\n";
    move_semantics_demo();
    
    std::cout << "\n=== Memory Alignment ===\n";
    alignment_demo();
    
    std::cout << "\n=== Custom Allocator ===\n";
    custom_allocator_demo();
    
    return 0;
}