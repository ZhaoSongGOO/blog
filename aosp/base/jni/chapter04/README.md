## JNIEnv 与 JavaVM


### JNIEnv 

JNIEnv 可以理解是一组函数构成的结构体，这些函数可以让你在 c 中操作 jvm 内部的状态。

#### JVM 特点

1. JNIEnv 线程局部的，不可以跨线程访问 、传递。

#### 如何获取 JNIEnv

1. 对于注册的 JNI 方法，会在调用的时候，传入 JNIEnv。
2. 对于其余的线程，可以通过 JavaVM 来获取 JNIEnv 对象。

```c
JavaVM* gJavaVM;

// 在 jni 调用的时候，通过env 获取到 JavaVM.
env->GetJavaVM(&gJavaVM);

// 其余地方/线程
JNIEnv * env;
gJavaVM->AttachCurrentrThread(&env, NULL);

gJavaVM->DetachCurrenrThread();

```

### JavaVM

JavaVM 表示的是 java 虚拟机本身。在一个进程中，只有一个虚拟机，即只有一个 JavaVM 对象。

#### 如何获取 JavaVM

1. 在动态注册阶段, 可以在 JNI_OnLoad 方法中获取到 JavaVM 对象。

2. 通过 JNIEnv 的 GetJavaVM 方法获取。

