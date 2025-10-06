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

### Looper 类 prepare 函数实现

Looper 对外提供的构造型 api 就是 prepare 和 prepareMainLooper。

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
    // 这个函数理论上只可在主线程调用一次
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

### Looper 构造函数

Looper 的构造函数为私有函数，会在创建自身的时候，创建一个 MessageQueue 对象。

```java
    private Looper() {
        mQueue = new MessageQueue();
        mRun = true;
        mThread = Thread.currentThread();
    }
```

MessageQueue 会在构造期间，调用 native 方法，创建对应的 c++ 对象。

```java
    @SuppressWarnings("unused")
    private int mPtr; // used by native code

    MessageQueue() {
        nativeInit();
    }
    private native void nativeInit();
```

这个 c++ 方法如下。

```cpp
static void android_os_MessageQueue_nativeInit(JNIEnv* env, jobject obj) {
    // 创建 c++ 版本的 MessageQueue NativeMessageQueue。
    NativeMessageQueue* nativeMessageQueue = new NativeMessageQueue();
    //...
    // 将这个 c++ 版本的 MessageQueue 和 java 版本的进行关联
    android_os_MessageQueue_setNativeMessageQueue(env, obj, nativeMessageQueue);
}

/*
GET_FIELD_ID(gMessageQueueClassInfo.mPtr, gMessageQueueClassInfo.clazz,
            "mPtr", "I");
*/
static void android_os_MessageQueue_setNativeMessageQueue(JNIEnv* env, jobject messageQueueObj,
        NativeMessageQueue* nativeMessageQueue) {
    // 把 java MessageQueue 对象的 mPtr 字段设置成 nativeMessageQueue 的地址
    env->SetIntField(messageQueueObj, gMessageQueueClassInfo.mPtr,
             reinterpret_cast<jint>(nativeMessageQueue));
}
```

下面，我们看下 NativeMessageQueue 的构造函数，它会在创建自身的时候，创建一个 c++ 版本的 Looper 对象。

```c++
NativeMessageQueue::NativeMessageQueue() {
    mLooper = Looper::getForThread(); // 判断当前线程是不是已经创建了 Looper 对象，这里 Looper 也是线程级别的实例。
    if (mLooper == NULL) {
        mLooper = new Looper(false);
        Looper::setForThread(mLooper);
    }
}
```

再进一步看一下 c++ Looper 的构造函数。

> [为什么管道描述符要设置成非阻塞模式?](android/framework/app_framework/message/ref/why_no_block_for_cpp_looper_fds.md)

```cpp
Looper::Looper(bool allowNonCallbacks) :
        mAllowNonCallbacks(allowNonCallbacks),
        mResponseIndex(0) {
    int wakeFds[2];
    // 创建匿名管道
    int result = pipe(wakeFds);
    LOG_ALWAYS_FATAL_IF(result != 0, "Could not create wake pipe.  errno=%d", errno);

    mWakeReadPipeFd = wakeFds[0];
    mWakeWritePipeFd = wakeFds[1];
    // 将读写描述符都设置成非阻塞模式
    result = fcntl(mWakeReadPipeFd, F_SETFL, O_NONBLOCK);
    LOG_ALWAYS_FATAL_IF(result != 0, "Could not make wake read pipe non-blocking.  errno=%d",
            errno);

    result = fcntl(mWakeWritePipeFd, F_SETFL, O_NONBLOCK);
    LOG_ALWAYS_FATAL_IF(result != 0, "Could not make wake write pipe non-blocking.  errno=%d",
            errno);
    //...
    // Allocate the epoll instance and register the wake pipe.
    // 创建一个 epoll 实例
    mEpollFd = epoll_create(EPOLL_SIZE_HINT);
    LOG_ALWAYS_FATAL_IF(mEpollFd < 0, "Could not create epoll instance.  errno=%d", errno);

    struct epoll_event eventItem;
    memset(& eventItem, 0, sizeof(epoll_event)); // zero out unused members of data field union
    eventItem.events = EPOLLIN;
    eventItem.data.fd = mWakeReadPipeFd;
    // 把读文件描述符加入 epoll 监控
    result = epoll_ctl(mEpollFd, EPOLL_CTL_ADD, mWakeReadPipeFd, & eventItem);
    LOG_ALWAYS_FATAL_IF(result != 0, "Could not add wake read pipe to epoll instance.  errno=%d",
            errno);
//...
}
```

## 线程消息循环过程

一个 Android 应用程序线程的消息队列创建完成之后，我们就可以调用 Looper 类的静态成员函数 loop 使它进入到一个消息循环中。

### Step1: Looper.loop

loop 函数内部就是直接拿出 MessageQueue，然后进入一个 while 循环，其中会阻塞在 MessageQueue 的 next 方法上。

```java
public static final void loop() {
    Looper me = myLooper();
    MessageQueue queue = me.mQueue;
    while (true) {
        Message msg = queue.next(); // might block
        //if (!me.mRun) {
        //    break;
        //}
        if (msg != null) {
            //...
        }
    }
}
```

### Step2: MessageQueue.next

```java
    final Message next() {
        // 这个变量在后面用来计算 idle handle 的数目
        /*
            当线程发现它的消息队列没有新的消息需要处理时，不是马上就进入睡眠等待状态，
            而是先调用注册到它的消息队列中的 IdleHandler 对象的成员函数 queueIdle，以便它们有机会在线程空闲时执行一些操作。
        */
        int pendingIdleHandlerCount = -1; // -1 only during first iteration
        // 这个用来计算睡眠策略，0 意味着不进入睡眠，-1 意味着无限睡眠，直到其他线程唤醒
        int nextPollTimeoutMillis = 0;

        // for 循环不断地调用成员函数 nativePollOnce 来检查当前线程的消息队列中是否有新的消息需要处理。
        for (;;) {
            // 如果需要进入睡眠，那就赶紧把那些 binder pending 的消息赶紧处理，避免长时间无法响应。
            if (nextPollTimeoutMillis != 0) {
                Binder.flushPendingCommands();
            }
            nativePollOnce(mPtr, nextPollTimeoutMillis);

            synchronized (this) {
                // Try to retrieve the next message.  Return if found.
                final long now = SystemClock.uptimeMillis();
                // 从 nativePollOnce 回来后，如果有消息，那 mMessages 不是 null
                final Message msg = mMessages;
                if (msg != null) {
                    final long when = msg.when;
                    // 判断这个消息是不是需要立刻处理
                    if (now >= when) {
                        mBlocked = false;
                        // 指向下一个消息
                        mMessages = msg.next;
                        msg.next = null;
                        if (Config.LOGV) Log.v("MessageQueue", "Returning message: " + msg);
                        return msg; // 返回消息
                    } else {
                        // 否则的话，需要睡眠一个时间，这个事件就是这个 message 设置的需要执行的时间差值。
                        nextPollTimeoutMillis = (int) Math.min(when - now, Integer.MAX_VALUE);
                    }
                } else {
                    // 否则的话，无限睡眠，直到有其他线程唤醒
                    nextPollTimeoutMillis = -1;
                }

                // If first time, then get the number of idlers to run.
                if (pendingIdleHandlerCount < 0) {
                    pendingIdleHandlerCount = mIdleHandlers.size();
                }
                if (pendingIdleHandlerCount == 0) {
                    // No idle handlers to run.  Loop and wait some more.
                    mBlocked = true;
                    continue;
                }

                if (mPendingIdleHandlers == null) {
                    mPendingIdleHandlers = new IdleHandler[Math.max(pendingIdleHandlerCount, 4)];
                }
                mPendingIdleHandlers = mIdleHandlers.toArray(mPendingIdleHandlers);
            }

            // 执行 idle handler，在一次 next 调用中，这个只会执行一次
            // Run the idle handlers.
            // We only ever reach this code block during the first iteration.
            for (int i = 0; i < pendingIdleHandlerCount; i++) {
                final IdleHandler idler = mPendingIdleHandlers[i];
                mPendingIdleHandlers[i] = null; // release the reference to the handler

                boolean keep = false;
                try {
                    keep = idler.queueIdle();
                } catch (Throwable t) {
                    Log.wtf("MessageQueue", "IdleHandler threw exception", t);
                }

                if (!keep) {
                    synchronized (this) {
                        mIdleHandlers.remove(idler);
                    }
                }
            }

            // Reset the idle handler count to 0 so we do not run them again.
            pendingIdleHandlerCount = 0;

            // While calling an idle handler, a new message could have been delivered
            // so go back and look again for a pending message without waiting.
            // 只要是执行了 idle，那这里不允许睡眠，因为可能其他线程已经发送了消息，需要立刻查看。
            nextPollTimeoutMillis = 0;
        }
    }
```

### Step3: nativePollOnce

```cpp
static void android_os_MessageQueue_nativePollOnce(JNIEnv* env, jobject obj,
        jint ptr, jint timeoutMillis) {
    NativeMessageQueue* nativeMessageQueue = reinterpret_cast<NativeMessageQueue*>(ptr);
    nativeMessageQueue->pollOnce(timeoutMillis);
}
```

### Step4: NativeMessageQueue.pollOnce

```cpp
void NativeMessageQueue::pollOnce(int timeoutMillis) {
    mLooper->pollOnce(timeoutMillis);
}
```

### Step5: Looper.pollOnce

循环不断地调用成员函数 pollInner 来检查当前线程是否有新的消息需要处理。如果有新的消息需要处理，那么成员函数 pollInner 的返回值就不会等于 0，这时候跳出 for 循环，以便当前线程可以对新的消息进行处理。

```cpp
int Looper::pollOnce(int timeoutMillis, int* outFd, int* outEvents, void** outData) {
    int result = 0;
    for (;;) {
        //...
        if (result != 0) {
            //...
            if (outFd != NULL) *outFd = 0;
            if (outEvents != NULL) *outEvents = NULL;
            if (outData != NULL) *outData = NULL;
            return result;
        }

        result = pollInner(timeoutMillis);
    }
}
```

### Step6: Looper.pollInner

```cpp
int Looper::pollInner(int timeoutMillis) {
    //...

    int result = ALOOPER_POLL_WAKE;
    //...
    struct epoll_event eventItems[EPOLL_MAX_EVENTS];
    // 如果这些文件描述符都没有发生 IO 读写事件，那么当前线程就会在函数 epoll_wait 中进入睡眠等待状态，等待的时间由最后一个参数 timeoutMillis 来指定。
    int eventCount = epoll_wait(mEpollFd, eventItems, EPOLL_MAX_EVENTS, timeoutMillis);
    //...
    for (int i = 0; i < eventCount; i++) {
        int fd = eventItems[i].data.fd;
        uint32_t epollEvents = eventItems[i].events;
        // 如果是 mWakeReadPipeFd 文件描述符的变动，而且是 EPOLLIN 事件，那就调用 awoken 方法
        if (fd == mWakeReadPipeFd) {
            if (epollEvents & EPOLLIN) {
                awoken();
            } 
            //...
        } 
        //...
    }
    //...
    return result;
}
```

### Step7: Looper.awoken

很神奇，这里就是不停的把数据读出来，也没存，也没解析。:)

```cpp
void Looper::awoken() {
    //...

    char buffer[16];
    ssize_t nRead;
    do {
        nRead = read(mWakeReadPipeFd, buffer, sizeof(buffer));
    } while ((nRead == -1 && errno == EINTR) || nRead == sizeof(buffer));
}
```

## 线程消息发送过程

Android 系统提供了一个 Handler 类，用来向一个线程的消息队列发送一个消息。Handler 类内部有 mLooper 和 mQueue 两个成员变量，它们分别指向一个 Looper 对象和一个 MessageQueue 对象。

Handler 类还有 sendMessage 和 handleMessage 两个成员函数，其中，成员函数 sendMessage 用来向成员变量 mQueue 所描述的一个消息队列发送一个消息；而成员函数 handleMessage 用来处理这个消息，并且它是在与成员变量 mLooper 所关联的线程中被调用的。

```java
public class Handler {
    public Handler() {
        //...
        mLooper = Looper.myLooper();
        //...
        mQueue = mLooper.mQueue;
        //...
    }

    public void handleMessage(Message msg) {
    }

    final MessageQueue mQueue;
    final Looper mLooper;
}
```

接下来，我们就从 Handler 类的成员函数 sendMessage 开始，分析向一个线程的消息队列发送一个消息的过程。

### Step1: Handler.sendMessage

这个直接把 Message 使用 MessageQueue 的 enqueueMessage 进行发送，需要注意的是 Message 的 target 设置成了当前的 handler 对象 this。

```java
public final boolean sendMessage(Message msg)
{
    return sendMessageDelayed(msg, 0);
}

public final boolean sendMessageDelayed(Message msg, long delayMillis)
{
    if (delayMillis < 0) {
        delayMillis = 0;
    }
    return sendMessageAtTime(msg, SystemClock.uptimeMillis() + delayMillis);
}

public boolean sendMessageAtTime(Message msg, long uptimeMillis)
{
    boolean sent = false;
    MessageQueue queue = mQueue;
    if (queue != null) {
        msg.target = this;
        sent = queue.enqueueMessage(msg, uptimeMillis);
    }
    else {
        //...
    }
    return sent;
}
```

### Step2: MessageQueue.enqueueMessage

```java
    final boolean enqueueMessage(Message msg, long when) {
        //...
        final boolean needWake;
        synchronized (this) {
            //...

            msg.when = when;
            //Log.d("MessageQueue", "Enqueing: " + msg);
            Message p = mMessages;
            /*
                p == null: 空队列
                when = 0: 当前消息需要立刻处理
                when < p.when: 当前消息处理时间早于队头消息的时间。

                这三种情况都直接插入队头。
            */
            if (p == null || when == 0 || when < p.when) {
                msg.next = p;
                mMessages = msg;
                // 需要唤醒，因为队头已经更改
                needWake = mBlocked; // new head, might need to wake up
            } else {
                Message prev = null;
                // 找到合适的位置
                while (p != null && p.when <= when) {
                    prev = p;
                    p = p.next;
                }
                msg.next = prev.next;
                prev.next = msg;
                // 队头没有更改，不需要唤醒
                needWake = false; // still waiting on head, no need to wake up
            }
        }
        // 如果需要唤醒，调用 nativeWake 方法。
        if (needWake) {
            nativeWake(mPtr);
        }
        return true;
    }
```

### Step3: MessageQueue.nativeWake

```cpp
static void android_os_MessageQueue_nativeWake(JNIEnv* env, jobject obj, jint ptr) {
    NativeMessageQueue* nativeMessageQueue = reinterpret_cast<NativeMessageQueue*>(ptr);
    return nativeMessageQueue->wake();
}
```

### Step4: NativeMessageQueue.wake

```cpp
void NativeMessageQueue::wake() {
    mLooper->wake();
}
```

### Step5: Looper::wake

就直接向那个管道的写 fd 写入一个 'W' 字符。只是起了一个唤醒(`epoll_wait` 返回)的作用。

```cpp
void Looper::wake() {
    //...
    ssize_t nWrite;
    do {
        nWrite = write(mWakeWritePipeFd, "W", 1);
    } while (nWrite == -1 && errno == EINTR);

    if (nWrite != 1) {
        if (errno != EAGAIN) {
            LOGW("Could not write wake signal, errno=%d", errno);
        }
    }
}
```

## 线程消息处理过程

### Step1: Looper.loop

被唤醒后，这里会调用 Message 中 target 的 dispatchMessage 方法，在前面我们知道，在 sendMessage 的时候，target 已经被设置成 Handler 对象的 this。

```java
    public static final void loop() {
        Looper me = myLooper();
        MessageQueue queue = me.mQueue;
        while (true) {
            Message msg = queue.next(); // 唤醒后，有消息，这里就返回了
            //if (!me.mRun) {
            //    break;
            //}
            if (msg != null) {
                if (msg.target == null) {
                    // No target is a magic identifier for the quit message.
                    return;
                }
                //...
                msg.target.dispatchMessage(msg);
                //...
            }
        }
    }
```

### Step2: Handler.dispatchMessage

```java
    public void dispatchMessage(Message msg) {
        // 如果要处理的消息在发送时指定了一个回调接口
        if (msg.callback != null) {
            handleCallback(msg);
        } else {
            // 如果 Handler 指定了自己的 mCallback，那就调用这个 mCallback 的 handleMessage 方法 如果返回 true，那就代表处理完毕，否则继续向下执行 handleMessage
            if (mCallback != null) {
                if (mCallback.handleMessage(msg)) {
                    return;
                }
            }
            handleMessage(msg);
        }
    }
```
#### handleCallback 调用

handleCallback 内部实现如下，直接调用 callback 的 run 方法。

```java
    private final void handleCallback(Message message) {
        message.callback.run();
    }
```

什么时候 msg 会有一个 callback 呢？ 我们的 handler 同时提供了一个 post 方法，这个方法接收一个 Runnable 类型的参数，如果我们使用 post 方法发送一个消息的话，Handler 内部就会把 Message 的 callback 设置成 Runnable 参数本身。

```java
    private final Message getPostMessage(Runnable r) {
        Message m = Message.obtain();
        m.callback = r;
        return m;
    }
    public final boolean post(Runnable r)
    {
       return  sendMessageDelayed(getPostMessage(r), 0);
    }
```

#### mCallback 调用

mCallback 的类型是一个 Handler.Callback，用户可以实现 Handler.Callback 这个接口，后续就可以进行消息的监听。

这个函数返回 true 意味着拦截，否则意味着继续传递给 Handler.handleMessage 方法。

```java
    public interface Callback {
        public boolean handleMessage(Message msg);
    }
```

#### Handler.handleMessage

这个方法在 Handler 基类中是空实现，需要我们自己的 handler 去独立实现。


## 线程空闲处理 idleHandler

> [为什么需要这个 idleHandler?](android/framework/app_framework/message/ref/idle_handler.md)

从上面分析，我们也可以看到一个线程中间因为等待消息的到来存在空闲的时间段，Android 提供了一种机制，可以让我们在这个空闲的时间段去执行一些任务，最大程度的优化性能。

MessageQueue 类有一个成员变量 mIdleHandlers，它指向了一个 IdleHandler 列表，用来保存一个线程的空闲消息处理器，以及对应的操作 api。

```java
public class MessageQueue {
    //...
    private final ArrayList<IdleHandler> mIdleHandlers = new ArrayList<IdleHandler>();
    //...
    public final void addIdleHandler(IdleHandler handler) {
        if (handler == null) {
            throw new NullPointerException("Can't add a null IdleHandler");
        }
        synchronized (this) {
            mIdleHandlers.add(handler);
        }
    }

    //...
    public final void removeIdleHandler(IdleHandler handler) {
        synchronized (this) {
            mIdleHandlers.remove(handler);
        }
    }
}
```

用户需要实现 IdleHandler 接口完成自己的 IdleHandler 定义。 这个接口的 queueIdle 返回 false 代表只执行一次，返回 true 代表再每一次 next 调用中都需要执行。

```java
    public static interface IdleHandler {
        boolean queueIdle();
    }
```

再次看一下 MessageQueue 的 next 方法。

```java
    final Message next() {
        //...
        int pendingIdleHandlerCount = -1; // -1 only during first iteration
        // 这个用来计算睡眠策略，0 意味着不进入睡眠，-1 意味着无限睡眠，直到其他线程唤醒
        int nextPollTimeoutMillis = 0;

        // for 循环不断地调用成员函数 nativePollOnce 来检查当前线程的消息队列中是否有新的消息需要处理。
        for (;;) {
            // 如果需要进入睡眠，那就赶紧把那些 binder pending 的消息赶紧处理，避免长时间无法响应。
            if (nextPollTimeoutMillis != 0) {
                Binder.flushPendingCommands();
            }
            nativePollOnce(mPtr, nextPollTimeoutMillis);

            synchronized (this) {
                //...

                // If first time, then get the number of idlers to run.
                if (pendingIdleHandlerCount < 0) {
                    pendingIdleHandlerCount = mIdleHandlers.size();
                }
                if (pendingIdleHandlerCount == 0) {
                    // No idle handlers to run.  Loop and wait some more.
                    mBlocked = true;
                    continue;
                }

                if (mPendingIdleHandlers == null) {
                    mPendingIdleHandlers = new IdleHandler[Math.max(pendingIdleHandlerCount, 4)];
                }
                mPendingIdleHandlers = mIdleHandlers.toArray(mPendingIdleHandlers);
            }

            // 执行 idle handler，在一次 next 调用中，这个只会执行一次
            // Run the idle handlers.
            // We only ever reach this code block during the first iteration.
            for (int i = 0; i < pendingIdleHandlerCount; i++) {
                final IdleHandler idler = mPendingIdleHandlers[i];
                mPendingIdleHandlers[i] = null; // release the reference to the handler

                boolean keep = false;
                try {
                    keep = idler.queueIdle();
                } catch (Throwable t) {
                    Log.wtf("MessageQueue", "IdleHandler threw exception", t);
                }
                // 不需要存储，那就删除
                if (!keep) {
                    synchronized (this) {
                        mIdleHandlers.remove(idler);
                    }
                }
            }

            // Reset the idle handler count to 0 so we do not run them again.
            pendingIdleHandlerCount = 0;

            // While calling an idle handler, a new message could have been delivered
            // so go back and look again for a pending message without waiting.
            // 只要是执行了 idle，那这里不允许睡眠，因为可能其他线程已经发送了消息，需要立刻查看。
            // 也是为了超时补偿。
            nextPollTimeoutMillis = 0;
        }
    }
```
