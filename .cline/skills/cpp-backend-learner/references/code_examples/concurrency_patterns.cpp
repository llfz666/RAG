/**
 * @file concurrency_patterns.cpp
 * @brief C++ 并发编程核心示例代码
 * 
 * 涵盖：线程基础、互斥锁、条件变量、原子操作、线程安全数据结构
 */

#include <iostream>
#include <thread>
#include <mutex>
#include <shared_mutex>
#include <atomic>
#include <condition_variable>
#include <queue>
#include <vector>
#include <chrono>
#include <functional>

// ============================================================================
// 1. 线程基础示例
// ============================================================================

void worker_function(int id) {
    std::cout << "Worker " << id << " started, thread id: " 
              << std::this_thread::get_id() << "\n";
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    std::cout << "Worker " << id << " finished\n";
}

void thread_basics_demo() {
    std::vector<std::thread> threads;
    
    // 创建多个线程
    for (int i = 0; i < 3; ++i) {
        threads.emplace_back(worker_function, i);
    }
    
    // 等待所有线程完成
    for (auto& t : threads) {
        t.join();
    }
    
    // detach 示例 - 分离线程
    std::thread([]() {
        std::cout << "Detached thread running\n";
    }).detach();
}

// ============================================================================
// 2. 互斥锁与 RAII 锁
// ============================================================================

class Counter {
    int value_ = 0;
    std::mutex mutex_;
    
public:
    void increment() {
        std::lock_guard<std::mutex> lock(mutex_);  // RAII 锁
        ++value_;
    }
    
    int get() {
        std::lock_guard<std::mutex> lock(mutex_);
        return value_;
    }
};

void mutex_demo() {
    Counter counter;
    std::vector<std::thread> threads;
    
    // 多个线程同时增加计数器
    for (int i = 0; i < 10; ++i) {
        threads.emplace_back([&counter]() {
            for (int j = 0; j < 1000; ++j) {
                counter.increment();
            }
        });
    }
    
    for (auto& t : threads) {
        t.join();
    }
    
    std::cout << "Counter value: " << counter.get() << " (expected: 10000)\n";
}

// ============================================================================
// 3. unique_lock 与条件变量
// ============================================================================

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
        // 等待队列非空
        cond_.wait(lock, [this] { return !queue_.empty(); });
        
        T value = std::move(queue_.front());
        queue_.pop();
        return value;
    }
    
    // 尝试弹出，不阻塞
    bool try_pop(T& value) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (queue_.empty()) {
            return false;
        }
        value = std::move(queue_.front());
        queue_.pop();
        return true;
    }
    
    bool empty() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.empty();
    }
};

void producer_consumer_demo() {
    ThreadSafeQueue<int> queue;
    std::atomic<bool> done{false};
    
    // 生产者
    std::thread producer([&queue, &done]() {
        for (int i = 0; i < 10; ++i) {
            queue.push(i);
            std::cout << "Produced: " << i << "\n";
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
        done = true;
    });
    
    // 消费者
    std::thread consumer([&queue, &done]() {
        while (!done || !queue.empty()) {
            int value;
            if (queue.try_pop(value)) {
                std::cout << "Consumed: " << value << "\n";
            } else {
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        }
    });
    
    producer.join();
    consumer.join();
}

// ============================================================================
// 4. 读写锁 (shared_mutex)
// ============================================================================

class ReadWriteData {
    int data_ = 0;
    mutable std::shared_mutex mutex_;
    
public:
    // 读操作 - 共享锁
    int read() const {
        std::shared_lock<std::shared_mutex> lock(mutex_);
        return data_;
    }
    
    // 写操作 - 独占锁
    void write(int value) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        data_ = value;
    }
};

void rw_lock_demo() {
    ReadWriteData data;
    std::vector<std::thread> threads;
    
    // 多个读线程
    for (int i = 0; i < 5; ++i) {
        threads.emplace_back([&data, i]() {
            for (int j = 0; j < 10; ++j) {
                int value = data.read();
                std::cout << "Reader " << i << " read: " << value << "\n";
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        });
    }
    
    // 一个写线程
    threads.emplace_back([&data]() {
        for (int i = 0; i < 5; ++i) {
            data.write(i);
            std::cout << "Writer wrote: " << i << "\n";
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
    });
    
    for (auto& t : threads) {
        t.join();
    }
}

// ============================================================================
// 5. 原子操作示例
// ============================================================================

class AtomicCounter {
    std::atomic<int> value_{0};
    
public:
    void increment() {
        ++value_;  // 原子操作
    }
    
    void add(int n) {
        value_.fetch_add(n, std::memory_order_relaxed);
    }
    
    int get() const {
        return value_.load(std::memory_order_relaxed);
    }
};

// CAS (Compare-And-Swap) 示例
class CasCounter {
    std::atomic<int> value_{0};
    
public:
    void increment() {
        int expected = value_.load();
        while (!value_.compare_exchange_weak(expected, expected + 1)) {
            // expected 会被更新为当前值，重试
        }
    }
    
    int get() const {
        return value_.load();
    }
};

void atomic_demo() {
    AtomicCounter atomic_counter;
    CasCounter cas_counter;
    std::vector<std::thread> threads;
    
    for (int i = 0; i < 10; ++i) {
        threads.emplace_back([&atomic_counter, &cas_counter]() {
            for (int j = 0; j < 1000; ++j) {
                atomic_counter.increment();
                cas_counter.increment();
            }
        });
    }
    
    for (auto& t : threads) {
        t.join();
    }
    
    std::cout << "Atomic counter: " << atomic_counter.get() << "\n";
    std::cout << "CAS counter: " << cas_counter.get() << "\n";
}

// ============================================================================
// 6. 线程安全单例模式
// ============================================================================

// C++11 起的线程安全单例 (Meyers' Singleton)
class Singleton {
public:
    static Singleton& instance() {
        static Singleton instance;  // 线程安全的局部静态变量
        return instance;
    }
    
    void do_something() {
        std::cout << "Singleton doing something\n";
    }
    
private:
    Singleton() = default;
    ~Singleton() = default;
    Singleton(const Singleton&) = delete;
    Singleton& operator=(const Singleton&) = delete;
};

void singleton_demo() {
    std::vector<std::thread> threads;
    
    for (int i = 0; i < 5; ++i) {
        threads.emplace_back([i]() {
            Singleton::instance().do_something();
        });
    }
    
    for (auto& t : threads) {
        t.join();
    }
}

// ============================================================================
// 7. 自旋锁实现
// ============================================================================

class SpinLock {
    std::atomic<bool> locked_{false};
    
public:
    void lock() {
        while (locked_.exchange(true, std::memory_order_acquire)) {
            // 自旋等待
        }
    }
    
    void unlock() {
        locked_.store(false, std::memory_order_release);
    }
};

class SpinLockCounter {
    int value_ = 0;
    SpinLock lock_;
    
public:
    void increment() {
        lock_.lock();
        ++value_;
        lock_.unlock();
    }
    
    int get() {
        lock_.lock();
        int v = value_;
        lock_.unlock();
        return v;
    }
};

void spinlock_demo() {
    SpinLockCounter counter;
    std::vector<std::thread> threads;
    
    for (int i = 0; i < 10; ++i) {
        threads.emplace_back([&counter]() {
            for (int j = 0; j < 1000; ++j) {
                counter.increment();
            }
        });
    }
    
    for (auto& t : threads) {
        t.join();
    }
    
    std::cout << "SpinLock counter: " << counter.get() << "\n";
}

// ============================================================================
// 8. 线程池简单实现
// ============================================================================

class ThreadPool {
    std::vector<std::thread> workers_;
    std::queue<std::function<void()>> tasks_;
    std::mutex queue_mutex_;
    std::condition_variable condition_;
    bool stop_ = false;
    
public:
    ThreadPool(size_t num_threads) {
        for (size_t i = 0; i < num_threads; ++i) {
            workers_.emplace_back([this] {
                while (true) {
                    std::function<void()> task;
                    {
                        std::unique_lock<std::mutex> lock(queue_mutex_);
                        condition_.wait(lock, [this] { 
                            return stop_ || !tasks_.empty(); 
                        });
                        
                        if (stop_ && tasks_.empty()) {
                            return;
                        }
                        
                        task = std::move(tasks_.front());
                        tasks_.pop();
                    }
                    task();
                }
            });
        }
    }
    
    template<typename F>
    void enqueue(F&& f) {
        {
            std::unique_lock<std::mutex> lock(queue_mutex_);
            tasks_.emplace(std::forward<F>(f));
        }
        condition_.notify_one();
    }
    
    ~ThreadPool() {
        {
            std::unique_lock<std::mutex> lock(queue_mutex_);
            stop_ = true;
        }
        condition_.notify_all();
        for (auto& worker : workers_) {
            worker.join();
        }
    }
};

void threadpool_demo() {
    ThreadPool pool(4);
    std::atomic<int> counter{0};
    
    for (int i = 0; i < 100; ++i) {
        pool.enqueue([&counter, i]() {
            std::cout << "Task " << i << " running\n";
            ++counter;
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        });
    }
    
    // 等待所有任务完成
    std::this_thread::sleep_for(std::chrono::milliseconds(2000));
    std::cout << "Completed tasks: " << counter << "\n";
}

// ============================================================================
// 主函数 - 运行所有示例
// ============================================================================

int main() {
    std::cout << "=== Thread Basics ===\n";
    thread_basics_demo();
    
    std::cout << "\n=== Mutex Demo ===\n";
    mutex_demo();
    
    std::cout << "\n=== Atomic Demo ===\n";
    atomic_demo();
    
    std::cout << "\n=== Singleton Demo ===\n";
    singleton_demo();
    
    std::cout << "\n=== SpinLock Demo ===\n";
    spinlock_demo();
    
    std::cout << "\n=== ThreadPool Demo ===\n";
    threadpool_demo();
    
    return 0;
}