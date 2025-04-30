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


### 属性与 SeLinux

### 属性系统源码分析

[ref](http://ahaoframework.tech/004.%E5%9F%BA%E7%A1%80%E7%BB%84%E4%BB%B6%E7%AF%87/012.%E5%A6%82%E4%BD%95%E6%B7%BB%E5%8A%A0%E7%B3%BB%E7%BB%9F%E5%B1%9E%E6%80%A7.html)

---

## Unix Domain Socket

Socket 本身是用来进行网络通信的机制，后面发展成一个 IPC 策略 UNIX domain socket . 且 UNIX domain socket  相比于 IP socket 去除了一些功能，更为精简，效率更高。

### UDP

<img src="aosp/componment/resources/c_5.png" style="width:50%"/>

#### 构建 socket

1. socket 构建完成后会返回一个文件描述符。
2. domain 代表 socket 类型，AF_INET,AF_INET6,AF_UNIX,分别对应 ipv4、ipv6 和 Unix Domain Socket。
3. type 代表选择 TCP 还是 UDP，SOCK_STREAM 意味着会提供按顺序的、可靠、双向、面向连接的比特流。SOCK_DGRAM 意味着会提供定长的、不可靠、无连接的通信。
4. protocol 一般设置为 0.

```c
#include <sys/types.h>
#include <sys/socket.h>

int socket (int domain, int type, int protocol)
```

#### bind

每一个 scoket 要能使用，就必须要和一个地址进行绑定，这就是 bind。

```c
int bind(int socket, const struct sockaddr *address, socklen_t address_len);
```

```c
char* server_file = "server.sock";
struct sockaddr_un addr;
memset(&addr,0,sizeof(addr));
addr.sun_family = AF_UNIX;
strcpy(addr.sun_path,server_file);
bind(fd,(sockaddr*)&addr,sizeof(addr));
```

#### sendto/recvfrom

```c
// 成功返回实际发送的数据长度，失败返回 -1
ssize_t sendto(int socket, const void *buffer, size_t length, int flags, const struct sockaddr *dest_addr, socklen_t dest_len);

ssize_t recvfrom(int socket, void *restrict buffer, size_t length, int flags, struct sockaddr *restrict address, socklen_t *restrict address_len);
```

##### `sendto`
- socket : socket 文件描述符。
- buffer : 要发送的数据。
- length : 消息长度。
- flags  : 设置成 0 即可。
- dest_addr/len : 目的地址/长度。


##### `recvfrom`
- socket : socket 文件描述符。
- buffer : 用来存放接收到的新消息。
- n : 接收到的信息的大小。
- flags : 操作位，取О就好。
- address/address_len : 接收到的消息的源地址，为了 server 可以对等的发回消息。


#### close

在使用完成后，需要关闭 socket，就和关闭文件一样。


### TCP

<img src="aosp/componment/resources/c_6.png" style="width:50%"/>


#### listen

listen 用来做 TCP 服务端的准备，其中 fd 是对应的 socket，n 代表最大连接数量。

```c
int listen (int fd, int n)
```

#### accept & connect

##### accept

listen 是为连接做准备，而 accept 则会等待新的连接，如果有新的连接，那就会返回一个新的连接的文件描述符。连接成功后，会将客户端的地址填充到 addr 的结构体上，字节大小填充到 addr_len。accept 返回的是客户端 socket fd.

```c
int accept(int socket, struct sockaddr *restrict address, socklen_t *restrict address_len);
```

##### connect

connect 是客户端专用，用于连接 server。connect 异常时返回-1，否则返回 0。地址在 addr 中指明。

```c
int connect(int socket, const struct sockaddr *address, socklen_t address_len);
```

##### recv & send

recv 和 send 的 socket 参数都是客户端 socket 描述符。

```c
ssize_t recv(int socket, void *buffer, size_t length, int flags);

ssize_t send(int socket, const void *buffer, size_t length, int flags);
```


### socket pair

---

## 日志系统

<img src="aosp/componment/resources/c_4.png" style="width:70%"/>


### 日志的类别与基本使用

> Android 系统中常见的日志有五类：main 、radio 、events 、system 、crash

#### main 

main 日志是应用层 APP 唯一可以使用的日志类型 (`android.util.Log`)。

```java
// 写 VERBOSE 等级的日志
Log.v("YOUR TAG", "Message body");
// 写 DEBUG 等级的日志
Log.d("YOUR TAG", "Message body");
// 写 INFO 等级的日志
Log.i("YOUR TAG", "Message body");
// 写 WARN 等级的日志
Log.w("YOUR TAG", "Message body");
// 写 ERROR 等级的日志
Log.e("YOUR TAG", "Message body");
```

在 native 层，我们也可以通过下面的方式来输出 main 日志。

```c
#define ALOGV(...) __android_log_print(ANDROID_LOG_VERBOSE, LOG_TAG, __VA_ARGS__)
#define ALOGD(...) __android_log_print(ANDROID_LOG_DEBUG  , LOG_TAG, __VA_ARGS__)
#define ALOGI(...) __android_log_print(ANDROID_LOG_INFO   , LOG_TAG, __VA_ARGS__)
#define ALOGW(...) __android_log_print(ANDROID_LOG_WARN   , LOG_TAG, __VA_ARGS__)
#define ALOGE(...) __android_log_print(ANDROID_LOG_ERROR  , LOG_TAG, __VA_ARGS__)
```

#### radio

顾名思义，radio日志主要用来记录无线装置/电话相关系统应用的日志，可以调用 `android.telephony.Rlog` 打印日志。

#### events

events 日志是用来诊断系统问题的。在应用框架提供了 `android.util.EventLog` 接口写日志，native 层提供了宏 `LOG_EVENT_INT、LOG_EVENT_LONG、LOG_EVENT_FLOAT、LOG_EVENT_STRING` 用来写入 events 类型日志。

#### system

system 日志主要用于记录系统应用的日志信息，在 Java 层提供了 `android.util.SLog` 接口写入日志， native 层提供了 `SLOGV、SLOGD、SLOGI、SLOGW、SLOGE` 等宏用来写入 system 类型的日志。

#### crash

crash 日志通常是程序 crash 时，记录的日志类型， Java 层使用 `Log.println()` （第一个参数设置为 `LOG_ID_CRASH`）打印 crash 类型的日志


### logcat 查看日志

```bash
logcat -b main
# 用来查看 main 和 system 类型日志
logcat -b main，system
logcat -b all #查看所有日志
```

### Kernel 日志

Kernel 层通常使用 `printk` 函数来记录日志，kernel 的所有日志信息存储在 `/proc/kmsg` 文件中。

```c
// KERN_INFO为日志级别，"Message body\n"则为日志信息
printk(KERN_INFO "Message body\n"); 

#define KERN_EMERGKERN_SOH "0"/* system is unusable */

#define KERN_ALERTKERN_SOH "1"/* action must be taken immediately */

#define KERN_CRITKERN_SOH "2"/* critical conditions */

#define KERN_ERRKERN_SOH "3"/* error conditions */

#define KERN_WARNINGKERN_SOH "4"/* warning conditions */

#define KERN_NOTICEKERN_SOH "5"/* normal but significant condition */

#define KERN_INFOKERN_SOH "6"/* informational */

#define KERN_DEBUGKERN_SOH "7"/* debug-level messages */
```
