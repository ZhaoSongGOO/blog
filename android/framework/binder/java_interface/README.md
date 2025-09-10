# Binder 通信的 Java 接口

## Service Manager 的 Java 代理对象的获取过程

> <img src="android/framework/binder/java_interface/resources/1.png" style="width:100%">

首先 Java 层提供了一个 ServiceManager 类，这是 Java 层用户与 SM 进行交互的门户。其中有一个方法 getIServiceManager 用以将建立 Java 与 c++ 中 SM 的关系。

```java
public final class ServiceManager {
    private static final String TAG = "ServiceManager";

    private static IServiceManager sServiceManager;
    //...
    private static IServiceManager getIServiceManager() {
        if (sServiceManager != null) {
            return sServiceManager;
        }
        sServiceManager = ServiceManagerNative.asInterface(BinderInternal.getContextObject());
        return sServiceManager;
    }
    //...
}
```

首先，去看下 BinderInternal 的 getContextObject 方法，这是一个 native 方法，那我们就去搜索一下在 c++ 中的定义。

```java
public static final native IBinder getContextObject();

// c++ 定义
static jobject android_os_BinderInternal_getContextObject(JNIEnv* env, jobject clazz)
{   
    // 获取 SM 的 IBinder
    sp<IBinder> b = ProcessState::self()->getContextObject(NULL);
    // 包装成 java 对象返回
    return javaObjectForIBinder(env, b);
}
```

介绍 javaObjectForIBinder 之前，我们先看三个数据结构。

1. `gBinderOffsets`

```cpp
static struct bindernative_offsets_t
{
    // Class state.
    jclass mClass; // 执行 java 层中的 Binder 类
    jmethodID mExecTransact;    // Binder 类的 execTransact 方法

    // Object state.
    jfieldID mObject;  // Binder 类的 mObject 成员

} gBinderOffsets;
```

2. `gBinderProxyOffsets`

```cpp
static struct binderproxy_offsets_t
{
    // Class state.
    jclass mClass; // Java 层 的 BinderProxy
    jmethodID mConstructor;  // BinderProxy 的构造方法
    jmethodID mSendDeathNotice;

    // Object state.
    jfieldID mObject;
    jfieldID mSelf;

} gBinderProxyOffsets;
```

3. `gWeakReferenceOffsets`

```cpp
static struct weakreference_offsets_t
{
    // Class state.
    jclass mClass; // 指向 java.lang.ref/WeakReference 类
    jmethodID mGet;

} gWeakReferenceOffsets;
```

接下来看 `javaObjectForIBinder` 这个函数的内容。


```cpp
jobject javaObjectForIBinder(JNIEnv* env, const sp<IBinder>& val)
{
    if (val == NULL) return NULL;

    // 如果传入的是一个 JavaBBinder 对象，这里 JavaBBinder 对象就是 BBinder 本地对象
    // 这也就说明了通过 java 注册的本地服务会在 c++ 这里对应一个 JavaBBinder 对象。
    if (val->checkSubclass(&gBinderOffsets)) {
        // One of our own!
        jobject object = static_cast<JavaBBinder*>(val.get())->object();
        //printf("objectForBinder %p: it's our own %p!\n", val.get(), object);
        return object;
    }

    // For the rest of the function we will hold this lock, to serialize
    // looking/creation of Java proxies for native Binder proxies.
    AutoMutex _l(mProxyLock);

    // Someone else's...  do we know about it?
    // 尝试找一下对应的 Java 层 BinderProxy 对象
    jobject object = (jobject)val->findObject(&gBinderProxyOffsets);
    if (object != NULL) {
        // 如果找到了，而且没有被释放，就直接返回。
        jobject res = env->CallObjectMethod(object, gWeakReferenceOffsets.mGet);
        if (res != NULL) {
            LOGV("objectForBinder %p: found existing %p!\n", val.get(), res);
            return res;
        }
        LOGV("Proxy object %p of IBinder %p no longer in working set!!!", object, val.get());
        android_atomic_dec(&gNumProxyRefs);
        val->detachObject(&gBinderProxyOffsets);
        env->DeleteGlobalRef(object);
    }
    // 创建一个新的 BinderProxy 对象
    object = env->NewObject(gBinderProxyOffsets.mClass, gBinderProxyOffsets.mConstructor);
    if (object != NULL) {
        LOGV("objectForBinder %p: created new %p!\n", val.get(), object);
        // The proxy holds a reference to the native object.
        // 这个 java 代理对象的 mObject 字段指向这个 c++ 代理对象的地址。
        env->SetIntField(object, gBinderProxyOffsets.mObject, (int)val.get());
        // 给这个 c++ 的代理对象增加强引用，因为 java 代理对象指向了它。
        val->incStrong(object);

        // The native object needs to hold a weak reference back to the
        // proxy, so we can retrieve the same proxy if it is still active.
        jobject refObject = env->NewGlobalRef(
                env->GetObjectField(object, gBinderProxyOffsets.mSelf));
        val->attachObject(&gBinderProxyOffsets, refObject,
                jnienv_to_javavm(env), proxy_cleanup);

        // Note that a new object reference has been created.
        android_atomic_inc(&gNumProxyRefs);
        incRefsCreated(env);
    }

    return object;
}
```

至此就会返回一个 Java 层的 `BinderProxy` 对象到 java 层，随后调用 `ServiceManagerNative.asInterface` 方法对其进行转换。

因为我们返回的是一个 BinderProxy ,所以 in 是 null，直接返回一个 ServiceManagerProxy 对象。
```java
    static public IServiceManager asInterface(IBinder obj)
    {
        if (obj == null) {
            return null;
        }
        IServiceManager in =
            (IServiceManager)obj.queryLocalInterface(descriptor);
        if (in != null) {
            return in;
        }
        
        return new ServiceManagerProxy(obj);
    }
```

到这里我们得到了什么呢？ 在 Java 层我们拿到了一个实现为 ServiceManagerProxy 的 IServiceManager，其中持有了一个 BinderProxy, 这个 BinderProxy 的 mObject 成员就是 c++ 那边 IBinder 对象的指针。

## Java 服务接口的定义和解析

在实现自己的 Java 服务之前，首先要定义这个 Java 服务要实现的接口，即定义自己的 Java 服务接口。在 Android 应用程序中，我们可以通过 Android 接口描述语言 (Android Interface Definition Language，AIDL) 来定义 Java 服务接口。AIDL 是一种 Binder 进程间通信接口的描述语言，通过它来定义的 Java 服务接口具有执行 Binder 进程间通信的能力。

以 AIDL 定义的 Java 服务接口保存在一个以 “.aidl” 为后缀名的文件中，在编译时，它们会被转化为使用Java语言来描述的Java服务接口。

```java
package android.os;

interface MyModule {
    void setVal(int val);
    int getVal();
}
```

通过下面的命令。

```bash
aidl -o gen \
     -I . \
     android/os/MyModule.aidl
```

生成的 Java 文件内容如下。

```java
package android.os;
// 这个就是我们用户定义的 Interface，类似于 C++ 中的 XXXInterface
public interface MyModule extends android.os.IInterface
{
  /** Default implementation for MyModule. */
  public static class Default implements android.os.MyModule
  {
    @Override public void setVal(int val) throws android.os.RemoteException
    {
    }
    @Override public int getVal() throws android.os.RemoteException
    {
      return 0;
    }
    @Override
    public android.os.IBinder asBinder() {
      return null;
    }
  }
  /** Local-side IPC implementation stub class. */
  // Stub 为本地服务，即实际的服务实现，用户需要继承自这个 Stub 实现具体的服务处理函数。
  public static abstract class Stub extends android.os.Binder implements android.os.MyModule
  {
    /** Construct the stub at attach it to the interface. */
    @SuppressWarnings("this-escape")
    public Stub()
    {
      this.attachInterface(this, DESCRIPTOR);
    }
    /**
     * Cast an IBinder object into an android.os.MyModule interface,
     * generating a proxy if needed.
     */
    public static android.os.MyModule asInterface(android.os.IBinder obj)
    {
      if ((obj==null)) {
        return null;
      }
      android.os.IInterface iin = obj.queryLocalInterface(DESCRIPTOR);
      if (((iin!=null)&&(iin instanceof android.os.MyModule))) {
        return ((android.os.MyModule)iin);
      }
      return new android.os.MyModule.Stub.Proxy(obj);
    }
    @Override public android.os.IBinder asBinder()
    {
      return this;
    }
    @Override public boolean onTransact(int code, android.os.Parcel data, android.os.Parcel reply, int flags) throws android.os.RemoteException
    {
      java.lang.String descriptor = DESCRIPTOR;
      if (code >= android.os.IBinder.FIRST_CALL_TRANSACTION && code <= android.os.IBinder.LAST_CALL_TRANSACTION) {
        data.enforceInterface(descriptor);
      }
      if (code == INTERFACE_TRANSACTION) {
        reply.writeString(descriptor);
        return true;
      }
      switch (code)
      {
        case TRANSACTION_setVal:
        {
          int _arg0;
          _arg0 = data.readInt();
          this.setVal(_arg0);
          reply.writeNoException();
          break;
        }
        case TRANSACTION_getVal:
        {
          int _result = this.getVal();
          reply.writeNoException();
          reply.writeInt(_result);
          break;
        }
        default:
        {
          return super.onTransact(code, data, reply, flags);
        }
      }
      return true;
    }
    // Java 本地的代理对象，类似于 c++ 中的 BpXXXX
    private static class Proxy implements android.os.MyModule
    {
      private android.os.IBinder mRemote; // 这个只能是一个 BinderProxy
      Proxy(android.os.IBinder remote)
      {
        mRemote = remote;
      }
      @Override public android.os.IBinder asBinder()
      {
        return mRemote;
      }
      public java.lang.String getInterfaceDescriptor()
      {
        return DESCRIPTOR;
      }
      @Override public void setVal(int val) throws android.os.RemoteException
      {
        android.os.Parcel _data = android.os.Parcel.obtain();
        android.os.Parcel _reply = android.os.Parcel.obtain();
        try {
          _data.writeInterfaceToken(DESCRIPTOR);
          _data.writeInt(val);
          boolean _status = mRemote.transact(Stub.TRANSACTION_setVal, _data, _reply, 0);
          _reply.readException();
        }
        finally {
          _reply.recycle();
          _data.recycle();
        }
      }
      @Override public int getVal() throws android.os.RemoteException
      {
        android.os.Parcel _data = android.os.Parcel.obtain();
        android.os.Parcel _reply = android.os.Parcel.obtain();
        int _result;
        try {
          _data.writeInterfaceToken(DESCRIPTOR);
          boolean _status = mRemote.transact(Stub.TRANSACTION_getVal, _data, _reply, 0);
          _reply.readException();
          _result = _reply.readInt();
        }
        finally {
          _reply.recycle();
          _data.recycle();
        }
        return _result;
      }
    }
    static final int TRANSACTION_setVal = (android.os.IBinder.FIRST_CALL_TRANSACTION + 0);
    static final int TRANSACTION_getVal = (android.os.IBinder.FIRST_CALL_TRANSACTION + 1);
  }
  /** @hide */
  public static final java.lang.String DESCRIPTOR = "android.os.MyModule";
  public void setVal(int val) throws android.os.RemoteException;
  public int getVal() throws android.os.RemoteException;
}

```

## Java 服务的启动和注册

### Java 服务的初始化

这个初始化的意思就是我们继承自 XXX.Stub 的类被构造时做的事情。

因为 XXX.Stub 继承自 `android.os.Binder`, 其会在 new 的时候调用到 `Binder` 的构造函数。这个构造方法中，会触发一个 native 方法 init。

```java
public Binder() {
    init();

    if (FIND_POTENTIAL_LEAKS) {
        final Class<? extends Binder> klass = getClass();
        if ((klass.isAnonymousClass() || klass.isMemberClass() || klass.isLocalClass()) &&
                (klass.getModifiers() & Modifier.STATIC) == 0) {
            Log.w(TAG, "The following Binder class should be static or leaks might occur: " +
                klass.getCanonicalName());
        }
    }
}

private native final void init();
```

在 c++ 中对应的逻辑 参数 clazz 指向的是前面在 Java 层中创建的硬件访问服务，以它为参数在C++层中创建了一个 JavaBBinderHolder 对象 jbh，接着增加了 JavaBBinderHolder 对象 jbh 的强引用计数，因为它被 Java 层中的硬件访问服务引用了。最后将 JavaBBinderHolder 对象 jbh 的地址值保存在硬件访问服务的父类 Binder 的成员变量 mObject 中。这样，运行在Java层中的硬件访问服务就可以通过它的成员变量 mObject 来访问运行在 C++ 层中的 JavaBBinderHolder 对象 jbh 了。

```cpp
static void android_os_Binder_init(JNIEnv* env, jobject clazz)
{
    JavaBBinderHolder* jbh = new JavaBBinderHolder(env, clazz);
    if (jbh == NULL) {
        jniThrowException(env, "java/lang/OutOfMemoryError", NULL);
        return;
    }
    LOGV("Java Binder %p: acquiring first ref on holder %p", clazz, jbh);
    jbh->incStrong(clazz);
    env->SetIntField(clazz, gBinderOffsets.mObject, (int)jbh);
}
```

这里 JavaBBinderHolder 是一个容器，其中存储着来自于 Java 的服务对应的 JObject 以及一个 c++ 对应的 JavaBBinder 对象。

```c++
class JavaBBinderHolder : public RefBase
{
public:
    JavaBBinderHolder(JNIEnv* env, jobject object)
        : mObject(object)
    {
        LOGV("Creating JavaBBinderHolder for Object %p\n", object);
    }
    ~JavaBBinderHolder()
    {
        LOGV("Destroying JavaBBinderHolder for Object %p\n", mObject);
    }

    sp<JavaBBinder> get(JNIEnv* env)
    {
        AutoMutex _l(mLock);
        sp<JavaBBinder> b = mBinder.promote();
        if (b == NULL) {
            b = new JavaBBinder(env, mObject);
            mBinder = b;
            LOGV("Creating JavaBinder %p (refs %p) for Object %p, weakCount=%d\n",
                 b.get(), b->getWeakRefs(), mObject, b->getWeakRefs()->getWeakCount());
        }

        return b;
    }

    sp<JavaBBinder> getExisting()
    {
        AutoMutex _l(mLock);
        return mBinder.promote();
    }

private:
    Mutex           mLock;
    jobject         mObject;
    wp<JavaBBinder> mBinder;
};
```

初始化完成后，就调用 `ServiceManager` 的 `addService` 方法将刚才的服务进行注册。

```java
public static void addService(String name, IBinder service) {
    try {
        getIServiceManager().addService(name, service);
    } catch (RemoteException e) {
        Log.e(TAG, "error in addService", e);
    }
}
```

回想一下，之前我们 `getIServiceManager` 方法返回的是 `ServiceManagerProxy`，其中持有一个 `BinderProxy` 对象。所以我们先去 `ServiceManagerProxy` 中查看对应的方法。

```java
public void addService(String name, IBinder service)
        throws RemoteException {
    Parcel data = Parcel.obtain();
    Parcel reply = Parcel.obtain();
    data.writeInterfaceToken(IServiceManager.descriptor);
    data.writeString(name);
    data.writeStrongBinder(service);
    mRemote.transact(ADD_SERVICE_TRANSACTION, data, reply, 0);
    reply.recycle();
    data.recycle();
}
```

类似于 C++ 层中的 Parcel 类，Java 层中的 Parcel 类也是用来封装进程间通信数据的。Java 层中的每一个 Parcel 对象在 C++ 层中都有一个对应的 Parcel 对象，后者的地址值就保存在前者的成员变量 mObject 中。当我们将进程间通信数据封装在一个 Java 层中的 Parcel 对象时，这个 Java 层中的 Parcel 对象就会通过其成员变量 mObject 找到与它对应的运行在 C++ 层中的 Parcel 对象，并且将这些进程间通信数据封装到 C++ 层中的 Parcel 对象里面去。

我们着重看一下 `Parcel` 的 `writeStrongBinder` 方法，这个方法依旧是一个 native 的方法。

```java
public final native void writeStrongBinder(IBinder val);

// native 方法
static void android_os_Parcel_writeStrongBinder(JNIEnv* env, jobject clazz, jobject object)
{
    Parcel* parcel = parcelForJavaObject(env, clazz);
    if (parcel != NULL) {
        const status_t err = parcel->writeStrongBinder(ibinderForJavaObject(env, object));
        if (err != NO_ERROR) {
            jniThrowException(env, "java/lang/OutOfMemoryError", NULL);
        }
    }
}
```

这个 `writeStrongBinder` 方法接收的参数是一个 c++ 的 IBinder 对象。所以 ibinderForJavaObject 就是来将一个 java 的 IBinder 对象转换成 c++ 的 IBinder 对象，在这个场景下就是继承自 java IBinder 的服务对象转换成 c++ JavaBBinder 对象。


```cpp
sp<IBinder> ibinderForJavaObject(JNIEnv* env, jobject obj)
{
    if (obj == NULL) return NULL;

    // 如果是一个来自于 Java 层的 Binder 实体对象
    if (env->IsInstanceOf(obj, gBinderOffsets.mClass)) {
        // 获取 JavaBBinderHolder 对象
        JavaBBinderHolder* jbh = (JavaBBinderHolder*)
            env->GetIntField(obj, gBinderOffsets.mObject);
        // get 返回其中的 JavaBinder 对象
        return jbh != NULL ? jbh->get(env) : NULL;
    }

    // 如果是一个来自于 Java 层的 BinderProxy 对象
    if (env->IsInstanceOf(obj, gBinderProxyOffsets.mClass)) {
        // 获取其中的 mObject 成员，这个是一个 c++ 的 IBinder 对象，可能是一个 BBinder 也可能是 BpBinder.
        return (IBinder*)
            env->GetIntField(obj, gBinderProxyOffsets.mObject);
    }

    LOGW("ibinderForJavaObject: %p is not a Binder object", obj);
    return NULL;
}
```

至此，我们完成了 Parcel 数据的写入，然后继续返回，我们看 `mRemote.transact(ADD_SERVICE_TRANSACTION, data, reply, 0)`。

之前提到了这个 `mRemote` 就是 `BinderProxy` 对象，它的 transact 方法是一个 jni 方法。从中可以看出，这里面最终注册的是这个 c++ 的 binder 实体对象，具体来说是 JavaBinder，而非 Java 层的服务实体。

```java
public native boolean transact(int code, Parcel data, Parcel reply,
            int flags) throws RemoteException;

// 对应的 c++ 方法
// params: c++ -> java
// obj -> BinderProxy 对象
// code -> code
// dataObj -> data
// replyObj -> reply
// flags -> flags
static jboolean android_os_BinderProxy_transact(JNIEnv* env, jobject obj,
                                                jint code, jobject dataObj,
                                                jobject replyObj, jint flags)
{
    if (dataObj == NULL) {
        jniThrowException(env, "java/lang/NullPointerException", NULL);
        return JNI_FALSE;
    }

    Parcel* data = parcelForJavaObject(env, dataObj);
    if (data == NULL) {
        return JNI_FALSE;
    }
    Parcel* reply = parcelForJavaObject(env, replyObj);
    if (reply == NULL && replyObj != NULL) {
        return JNI_FALSE;
    }
    // BinderProxy 中的 mObject 存储的是一个 c++ IBinder 对象的指针
    IBinder* target = (IBinder*)
        env->GetIntField(obj, gBinderProxyOffsets.mObject);
    if (target == NULL) {
        jniThrowException(env, "java/lang/IllegalStateException", "Binder has been finalized!");
        return JNI_FALSE;
    }

    LOGV("Java code calling transact on %p in Java object %p with code %d\n",
            target, obj, code);

    // Only log the binder call duration for things on the Java-level main thread.
    // But if we don't
    const bool time_binder_calls = should_time_binder_calls();

    int64_t start_millis;
    if (time_binder_calls) {
        start_millis = uptimeMillis();
    }
    //printf("Transact from Java code to %p sending: ", target); data->print();
    // 发送消息。
    status_t err = target->transact(code, *data, reply, flags);
    //if (reply) printf("Transact from Java code to %p received: ", target); reply->print();
    if (time_binder_calls) {
        conditionally_log_binder_call(start_millis, target, code);
    }

    if (err == NO_ERROR) {
        return JNI_TRUE;
    } else if (err == UNKNOWN_TRANSACTION) {
        return JNI_FALSE;
    }

    signalExceptionForError(env, obj, err);
    return JNI_FALSE;
}
```

## Java 服务代理对象的获取







