# 系统启动


<img src="aosp/launch/resources/launch_1.png"/>

Android 系统启动本身就是一个 Linux 系统启动的标准流程。

## Boot ROM 加载并执行

类似于我们 PC 启动会进入 bios 一样，手机启动也会由硬件控制上电执行 Boot ROM 的逻辑，在 Boot ROM 中，会进行一些硬件检测任务，随后加载 BootLoader 到内存中，并跳转到 BootLoader 的逻辑。

## BootLoader 执行

BootLoader 会进一步的进行设备的检测，随后加载内核到内存中，并跳转到内核逻辑执行。


## Kernel 执行

和 Linux kernel 一样，内核都是多阶段加载的方式来执行，内核最初的部分会初始化中断向量，随后初始化 c 环境，并创建好第一个进程 Swapper。这个进程是所有 Android 进程的祖先。

## Swapper 进程

Swapper 进程是一个内核进程，其会执行如下操作：
1. 初始化内存管理 、文件系统 、进程管理逻辑，这代表整个内核的功能初始化完毕。
2. 加载硬件驱动。
3. 创建其余的内核进程。
4. 创建第一个用户空间进程 init 进程。

## init 进程

init 进程是所有用户空间进程的祖先。init 进程除了做一些初始化操作外，还会创建一系列的 native 守护进程，例如 binder 中的 service-manager，abdb 进程用于 adb 调试通信。还有一个重要的进程 zygote.

## Zygote 进程

Zygote 进程是所有 andoroid 应用的父进程。所有的 android 应用都由其 fork 出来。在 zygote初始化后，其会做如下操作：

1. 加载 java 库资源以及 android 资源，为的是后面 fork 出来应用，可以复用，提升 app 启动速度。
2. 初始化系统服务。
3. 监听应用创建信息。
