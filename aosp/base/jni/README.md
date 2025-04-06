# JNI

## 什么是 jni

jni 全称是 java native interface, 即 java 与 原生接口，这里原生可以理解成 C++。其本身是 jvm 提供的一种能力，允许我们在 java语言中直接调用 C++ 逻辑，同时也允许 C++ 调用 java 逻辑 (和 jsi 一样)。

我们使用 jni 的原因有如下几个：
1. 必要性：很多基础模块都是 c 或者 c++ 编写的，我们想要调用这些能力，必须提供一个 java 与 C++ 通信的机制。
2. 优化：大多数时候，c 或者 c++ 编写的模块性能更加优异，因此为了追求性能，将具体执行放到 c 层。
3. 可移植：如果我们有一个通用的功能，不仅想用在 Android 系统上，还想迁移到其他的平台，例如 iOS，那此时我们就需要把 Java 实现的逻辑改成 OC 再实现一遍，那带来的是成倍的开发成本和维护成本。但是如果我们使用 c 编写，那两个平台可以共享一份 c 层的逻辑。


## [JNI 极速上手](aosp/base/jni/chapter01/)
## [JNI 数据类型](aosp/base/jni/chapter02/)
## [如何在 native 中找到 Java 中的属性](aosp/base/jni/chapter03/)
## [JNIEnv 与 JavaVM](aosp/base/jni/chapter04/)
## [字符串和数组访问](aosp/base/jni/chapter05/)
## [Native 访问 Java](aosp/base/jni/chapter06/)
## [异常处理](aosp/base/jni/chapter07/)

