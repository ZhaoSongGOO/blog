# 准备知识

### 资料

1. Linux 内核

Android 系统本质是一个 Linux 内核的二次开发，因此我们需要准备一些 Linux 内核相关的知识。

- Linux Kernel Development, 这本书对Linux内核的设计原理和实现思路提供了一个总览视图，并且对Linux内核的各个子系统的设计目标进行了清晰的描述，非常适合初学者阅读。从软件工程的角度来看，这本书相当于Linux内核的概要设计文档。

- Understanding the Linux Kernel, 这本书对Linux内核的实现提供了更多的细节，详细地描述了内核开发中用到的各种重要数据结构、算法以及编程技巧等，非常适合中、高级读者阅读。从软件工程的角度来看，这本书相当于Linux内核的详细设计文档。

- Linux Device Drivers, 偏实践的一本书。

- Linux内核源代码情景分析, 系统详细的介绍 Linux 内核源代码，是一个代码阅读指南。

2. Android 平台开发

- https://source.android.com/?hl=zh-cn , Android 框架开发官网。

- https://developer.android.com/?hl=zh-cn, Android 应用开发官网。

### Android 生态架构

<img src="android/framework/resources/android-stack.svg" style="width:40%">

- Android API: Android API 是面向第三方 Android 应用开发者的公开 API。

- System API: 系统 API 表示仅供合作伙伴和 OEM 纳入捆绑应用的 Android API。这些 API 在源代码中被标记为 @SystemApi。

- Android Apps: 纯粹使用 Android API 开发的应用软件，从谷歌或者其他应用商场直接下载。

- Privilege Apps & Device Manufacture Apps: 特权应用，使用 Android API 和系统 API 创建的应用，一般是设备预安装应用。例如摄像机、相册等。

- Android Framework: Android API 底层实现，以及应用的 Java 以及 C++ 框架。

- Android Runtime: Android 特有的运行 Java 字节码的 JVM。

- HAL:HAL 是一个抽象层，其中包含硬件供应商要实现的标准接口。HAL 让 Android 无需关注较低级别的驱动程序实现。

- Kernel: liunx kernel fork 版。
