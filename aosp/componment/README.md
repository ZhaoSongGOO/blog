# 基础组件

## 智能指针

## eventfd

## epoll 多路复用

## timerfd 

## Android Native Looper 机制

<img src="aosp/componment/resources/c_1.png" style="width:30%"/>

android 的 native looper 由 eventfd 和 epoll 来统一实现。在 android 中，这套循环机制叫 Looper。

### Looper 的基础用法

```cpp
// 创建Looper对象
sp<Looper> mLooper = Looper::prepare(false /*allowNonCallbacks*/);

// 添加/删除要检测的文件描述符，可以添加一个回调对象，当对应事件发生时，调用回调对象中的回调函数
mLooper->addFd(fd, 0, ALOOPER_EVENT_INPUT, handleReceiveCallback, this);
mLooper->removeFd(inputChannel->getFd());

// 进入休眠状态等待回调、超时或唤醒
mLooper->pollAll(timeoutMillis);

// 主动唤醒
mLooper->wake();

// 发送、删除消息
mLooper->sendMessage(handler, message);
```

### Looper 的基础流程

1. 调用 prepare 初始化 looper。
2. 使用 addFd 增加自己想要观察的文件描述符。
> 这里以 server-manager 为例，其想观察的文件描述符一个是 binder fd，一个是 timerfd。
> 关注 binder-fd 是为了在 binder 收到数据后被唤醒。
> 关注 timerfd 是为了执行一些定期的处理工作。
3. 进入循环，等待唤醒。

```cpp
// frameworks/native/cmds/servicemanager/main.cpp

// 只摘取了 Looper 相关代码
int main(int argc, char** argv) {

    sp<Looper> looper = Looper::prepare(false /*allowNonCallbacks*/);

    BinderCallback::setupTo(looper);
    ClientCallbackCallback::setupTo(looper, manager);

    while(true) {
        // 进入休眠状态等待回调、超时或唤醒
        looper->pollAll(-1);
    }
}

// 绑定 binder 对应的 fd，当 binder fd 可读时，唤醒 epoll，调用回调函数
static sp<BinderCallback> setupTo(const sp<Looper>& looper) {
    sp<BinderCallback> cb = sp<BinderCallback>::make();

    int binder_fd = -1;
    IPCThreadState::self()->setupPolling(&binder_fd);
    LOG_ALWAYS_FATAL_IF(binder_fd < 0, "Failed to setupPolling: %d", binder_fd);

    int ret = looper->addFd(binder_fd,
                            Looper::POLL_CALLBACK,
                            Looper::EVENT_INPUT,
                            cb,
                            nullptr /*data*/);
    LOG_ALWAYS_FATAL_IF(ret != 1, "Failed to add binder FD to Looper");

    return cb;
}

// 绑定一个 timerfd，每间隔 5 秒，epoll 唤醒一次，调用回调函数
static sp<ClientCallbackCallback> setupTo(const sp<Looper>& looper, const sp<ServiceManager>& manager) {
    sp<ClientCallbackCallback> cb = sp<ClientCallbackCallback>::make(manager);

    int fdTimer = timerfd_create(CLOCK_MONOTONIC, 0 /*flags*/);
    LOG_ALWAYS_FATAL_IF(fdTimer < 0, "Failed to timerfd_create: fd: %d err: %d", fdTimer, errno);

    itimerspec timespec {
        // 设置超时间隔
        .it_interval = {
            .tv_sec = 5,
            .tv_nsec = 0,
        },
        //第一次超时时间
        .it_value = {
            .tv_sec = 5,
            .tv_nsec = 0,
            },
    };

    int timeRes = timerfd_settime(fdTimer, 0 /*flags*/, &timespec, nullptr);
    LOG_ALWAYS_FATAL_IF(timeRes < 0, "Failed to timerfd_settime: res: %d err: %d", timeRes, errno);

    int addRes = looper->addFd(fdTimer,
                                Looper::POLL_CALLBACK,
                                Looper::EVENT_INPUT,
                                cb,
                                nullptr);
    LOG_ALWAYS_FATAL_IF(addRes != 1, "Failed to add client callback FD to Looper");
    return cb;
}
```

### Looper 被唤醒

Looper 有两种唤醒的原因：
1. 其余线程发送 Message 以唤醒。

其余线程发送消息后，会触发 eventfd 的变化来唤醒 Looper 中的 epoll_wait。

2. 关注的文件描述符产生变化以唤醒 Response。


## Android Java Looper 机制


<img src="aosp/componment/resources/c_2.png" style="width:70%"/>

```java
// 典型的关于Handler/Looper的线程
class LooperThread extends Thread {

    public Handler mHandler;

    public void run() {
       
        Looper.prepare();   
        
        mHandler = new Handler() {  
            public void handleMessage(Message msg) {
                //定义消息处理逻辑. 
                Message msg = Message.obtain();
            }
        };

        Looper.loop();  
    }
}

// 其他线程
Message msg = Message.obtain();
msg.what = 2; 
msg.obj = "B"; 
// 向 looper 发送一个消息
looperThread.mHandler.sendMessage(msg);
```


## Handler 同步屏障机制

### 机制

Handler 发送消息的时候，默认发送的是同步消息，这种消息会按照顺序执行。但是我们有时可能需要发送一些高优先级的消息，这些消息被称为异步消息。这些消息在正常情况下没有任何的差异，但是当 Handler 中存在屏障的时候，就有不一样的行为了。

- 当我们使用屏障的时候，消息队列中的所有同步消息都不会处理，直到屏障解除。
- 当使用屏障的时候，异步消息则可以通过屏障，直接处理。

### 使用场景

当系统需要进行 UI 绘制的时候，UI 因为和用户的交互息息相关，所以其具有较高的执行优先级，而且为了避免卡顿，最好进行完整的不中断执行(不要被其他非 UI 任务干扰)。

所以 Android 的设计中，就会在 VSync 触发的时候，在主线程的任务队列中设置屏障，阻止其余任务执行，而将 UI 任务全部以异步任务的方式触发，从而确保 UI 任务的快速连贯执行。



## IdleHandler 

### 什么是 IdleHandler

IdleHandler 是一种特殊的任务，这些任务会在 Loop 中任务队列为空的时候进行触发。

### 使用场景

GCIdle, 这个任务看名字就知道执行一些垃圾回收的处理，这些任务会发生在当前线程空闲的时候。


## Android 属性系统

在 Android 系统中，为统一管理系统的属性，设计了一个统一的属性系统，每个属性都是一个 key-value 对。 我们可以通过 shell 命令，Native 函数接口，Java 函数接口的方式来读写这些 key-vaule 对。

### 加载

init 进程会在启动的时候去搜索 `*.prop` 文件来解析系统属性。

```c
void property_load_boot_defaults(bool load_debug_prop) {
    // TODO(b/117892318): merge prop.default and build.prop files into one
    // We read the properties and their values into a map, in order to always allow properties
    // loaded in the later property files to override the properties in loaded in the earlier
    // property files, regardless of if they are "ro." properties or not.
    std::map<std::string, std::string> properties;
    if (!load_properties_from_file("/system/etc/prop.default", nullptr, &properties)) {
        // Try recovery path
        if (!load_properties_from_file("/prop.default", nullptr, &properties)) {
            // Try legacy path
            load_properties_from_file("/default.prop", nullptr, &properties);
        }
    }
    load_properties_from_file("/system/build.prop", nullptr, &properties);
    load_properties_from_file("/vendor/default.prop", nullptr, &properties);
    load_properties_from_file("/vendor/build.prop", nullptr, &properties);
    if (SelinuxGetVendorAndroidVersion() >= __ANDROID_API_Q__) {
        load_properties_from_file("/odm/etc/build.prop", nullptr, &properties);
    } else {
        load_properties_from_file("/odm/default.prop", nullptr, &properties);
        load_properties_from_file("/odm/build.prop", nullptr, &properties);
    }
    load_properties_from_file("/product/build.prop", nullptr, &properties);
    load_properties_from_file("/product_services/build.prop", nullptr, &properties);
    load_properties_from_file("/factory/factory.prop", "ro.*", &properties);

    if (load_debug_prop) {
        LOG(INFO) << "Loading " << kDebugRamdiskProp;
        load_properties_from_file(kDebugRamdiskProp, nullptr, &properties);
    }

    for (const auto& [name, value] : properties) {
        std::string error;
        if (PropertySet(name, value, &error) != PROP_SUCCESS) {
            LOG(ERROR) << "Could not set '" << name << "' to '" << value
                       << "' while loading .prop files" << error;
        }
    }

    property_initialize_ro_product_props();
    property_derive_build_fingerprint();

    update_sys_usb_config();
}
```

每一个 prop 文件的内容就是一些以行为单位的键值对。

```bash
ro.actionable_compatible_property.enabled=true
ro.postinstall.fstab.prefix=/system
ro.secure=0
ro.allow.mock.location=1
ro.debuggable=1
debug.atrace.tags.enableflags=0
dalvik.vm.image-dex2oat-Xms=64m
dalvik.vm.image-dex2oat-Xmx=64m
```

### 读写

#### shell

```bash
getprop "wlan.driver.status"
setprop "wlan.driver.status"  "timeout"
```

#### c

```c
char buf[20]="qqqqqq";
char tempbuf[PROPERTY_VALUE_MAX];
property_set("type_value",buf);
property_get("type_value",tempbuf,"0");
```

#### java

```java
String navBarOverride = SystemProperties.get("qemu.hw.mainkeys");
SystemProperties.set("service.bootanim.exit", "0");
```

### 增加属性

#### 增加 System 属性

```makefile
TARGET_SYSTEM_PROP += device/jelly/rice14/system.prop
```

#### 增加Vendor属性

```makefile
PRODUCT_PROPERTY_OVERRIDES += \
    ro.vendor.xxx=xxx \
    ro.vendor.yyy=yyy
```

#### 增加 Product 属性

```makefile
PRODUCT_PRODUCT_PROPERTIES += \
     ro.product.xxx=xxx \
     ro.product.yyy=yyy
```

### 属性系统整体架构

<img src="aosp/componment/resources/c_3.png" style="width:70%"/>

1. Android 系统启动时会从若干属性配置文件中加载属性内容，所有属性（key/value）和属性安全上下文信息会存入 /dev/__property__ 下的各个文件中。
2. 系统中的各个进程会通过 mmap 将 /dev/__property__ 下的各个文件映射到自己的内存空间，这样就可以直接读取属性内容了。
3. 系统中只有 init 进程可以直接写属性值，其他进程不能直接修改属性值。
4. init 进程启动了一个 Socket 服务端，一般称为 Property Service，其他进程通过 socket 方式，向 Property Service 发出属性修改请求。
5. /dev/__property__目录下文件中的数据会以字典二叉混合树的形式进行组织。

### 属性系统源码分析

TODO


## Unix Domain Socket

### UDP

### TCP

### socket pair


## 日志系统



