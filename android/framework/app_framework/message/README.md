# Android 应用程序的消息处理机制

我们知道，Android 应用程序是通过消息来驱动的。Android 应用程序的每一个线程在启动时，都可以首先在内部创建一个消息队列，然后再进入到一个无限循环中，不断检查它的消息队列是否有新的消息需要处理。如果有新的消息需要处理，那么线程就会将它从消息队列中取出来，并且对它进行处理；否则，线程就会进入睡眠等待状态，直到有新的消息需要处理为止。这样就可以通过消息来驱动 Android 应用程序的执行了。

Android 应用程序的消息处理机制是围绕消息队列来实现的。一个线程拥有一个消息队列之后，就可以进入到一个消息循环中，同时其他线程以及线程本身可以往这个消息队列发送消息，以便可以在这个消息被处理时执行一个特定的操作。这样我们就将一个线程的生命周期划分为创建消息队列和进入消息循环两个阶段，其中，消息循环阶段又划分为发送消息和处理消息两个子阶段，它们是交替进行的。

Android 系统主要通过 MessageQueue、Looper 和 Handler 三个类来实现 Android 应用程序的消息处理机制，其中，MessageQueue 类用来描述消息队列；Looper 类用来创建消息队列，以及进入消息循环；Handler 类用来发送消息和处理消息。接下来，我们首先分析线程消息队列的创建过程，然后分析线程的消息循环过程，最后分析线程消息的发送和处理过程。

## 创建线程消息队列

Android 应用程序线程的消息队列是使用一个 MessageQueue 对象来描述的，它可以通过调用 Looper 类的静态成员函数 prepareMainLooper 或者 prepare 来创建，其中，前者用来为应用程序的主线程创建消息队列；而后者用来为应用程序的其他子线程创建消息队列。

### Looper 类和 MessageQueue 类的总览

<img src="android/framework/app_framework/message/resources/1.png" style="width:50%">

Android 应用程序的消息处理机制不仅可以在 Java 代码中使用，也可以在 C++代码中使用，因此，Android 系统在 C++层中也有一个相应的 Looper 类和 NativeMessageQueue 类。其中，Java 层中的 Looper 类和 MessageQueue 类是通过 C++层中的 Looper 类和 NativeMessageQueue 类来实现的。

Java 层中的每一个 Looper 对象内部都有一个类型为 MessageQueue 的成员变量 mQueue，它指向了一个 MessageQueue 对象；而在 C++层中，每一个 NativeMessageQueue 对象内部都有一个类型为 Looper 的成员变量 mLooper，它指向了一个 C++层的 Looper 对象。

Java 层中的每一个 MessageQueue 对象都有一个类型为 int 的成员变量 mPtr，它保存了 C++层中的一个 NativeMessageQueue 对象的地址值，这样我们就可以将 Java 层中的一个 MessageQueue 对象与 C++层中的一个 NativeMessageQueue 对象关联起来。

Java 层中的每一个 MessageQueue 对象还有一个类型为 Message 的成员变量 mMessages，它用来描述一个消息队列，我们可以调用 MessageQueue 类的成员函数 enqueueMessage 来往里面添加一个消息。

C++层中的 Looper 对象有两个类型为 int 的成员变量 mWakeReadPipeFd 和 mWakeWritePipeFd，它们分别用来描述一个管道的读端文件描述符和写端文件描述符。当一个线程的消息队列没有消息需要处理时，它就会在这个管道的读端文件描述符上进行睡眠等待，直到其他线程通过这个管道的写端文件描述符来唤醒它为止。

当我们调用 Java 层的 Looper 类的静态成员函数 prepareMainLooper 或者 prepare 来为一个线程创建一个消息队列时，Java 层的 Looper 类就会在这个线程中创建一个 Looper 对象和一个 MessageQueue 对象。在创建 Java 层的 MessageQueue 对象的过程中，又会调用它的成员函数 nativeInit 在 C++层中创建一个 NativeMessageQueue 对象和一个 Looper 对象。在创建 C++层的 Looper 对象时，又会创建一个管道，这个管道的读端文件描述符和写端文件描述符就保存在它的成员变量 mWakeReadPipeFd 和 mWakeWritePipeFd 中。

Java 层中的 Looper 类的成员函数 loop、MessageQueue 类的成员函数 nativePollOnce 和 nativeWake，以及 C++层中的 NativeMessageQueue 类的成员函数 pollOnce 和 wake、Looper 类的成员函数 pollOnce 和 wake，是与线程的消息循环、消息发送和消息处理相关的。

### Looper 类创建队列函数实现

```java
public class Looper {
    //...
    private static final ThreadLocal sThreadLocal = new ThreadLocal(); // 每个线程都会有一个独立的实例

    final MessageQueue mQueue;
    //...
    private static Looper mMainLooper = null;
    
    //...
    public static final void prepare() {
        // 检查是否有 looper 已经创建了，创建就爆出异常
        if (sThreadLocal.get() != null) {
            throw new RuntimeException("Only one Looper may be created per thread");
        }
        // 存储常见的 looper
        sThreadLocal.set(new Looper());
    }
    
    //...
    public static final void prepareMainLooper() {
        prepare();
        setMainLooper(myLooper());
        if (Process.supportsProcesses()) {
            myLooper().mQueue.mQuitAllowed = false;
        }
    }
    // 将这个 Looper 对象保存在 Looper 类的静态成员变量 mMainLooper 中。
    private synchronized static void setMainLooper(Looper looper) {
        mMainLooper = looper;
    }
    
    //...
    public synchronized static final Looper getMainLooper() {
        return mMainLooper;
    }

    public static final Looper myLooper() {
        return (Looper)sThreadLocal.get();
    }
    //...
}
```