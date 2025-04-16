# Binder

## What is binder?

Binder 是 Android 系统中的一套 进程间通信（IPC） 框架，其命名源于底层依赖 Linux 内核的 Binder 驱动。
Binder 驱动的核心功能包括：

- 服务注册与发现：允许一个 Service Manager（早期版本中的核心组件）统一管理多个 Server 服务。

- 跨进程调用：Client 可通过 Binder 驱动查询到目标 Server 的引用（以 Binder Proxy 形式返回），并通过该引用发起远程方法调用（RPC）。

- 高效数据传输：Binder 利用内存映射（mmap）机制在进程间共享数据，仅需一次拷贝（从发送方用户空间到内核空间，接收方直接访问映射的内核缓冲区），相比传统 IPC（如管道/Socket）减少数据拷贝次数，从而提升性能。

<img src="aosp/binder/resources/binder_2.png" style="width:50%"/>

<img src="aosp/binder/resources/binder_1.png" style="width:70%"/>

从架构图中可以看到 binder 横跨了应用层到内核层，是维持整个系统通信链路的基石。

- 内核层： binder 底层驱动由内核管理，并暴露出方便使用 binder 的 libbinder 库。
- native层：在 server manager 由 native 层实现。同时也实现了一些 native 版本的 client 和 server。
- jni层：通过对 libbinder 封装，暴露给 java 层使用。
- java层：借助于 jni 的接口，可以对 native server进行调用，也可以实现 java 版本的 client 和 server。
