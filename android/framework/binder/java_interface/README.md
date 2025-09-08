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
      private android.os.IBinder mRemote; // 这个可能是一个 BinderProxy 或者 MyModule 实例
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




