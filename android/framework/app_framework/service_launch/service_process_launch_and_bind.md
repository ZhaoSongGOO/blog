# Service 组件同进程的绑定过程

本小节主要介绍了一个同进程的 Service 使用 bind 操作进行启动获取长连接的过程。

我们首先花一点篇幅来讲解一下这种 bind 类型的 service 如何实现。

## 可绑定式服务的实现

```java
class MyService : Service() {
    private val mBinder = DownloadBinder()
    
    // 首先我们在 service 中实现一个 binder，并在 onBind 方法中返回这个对象的实例
    class DownloadBinder : Binder() {

        fun startDownload() {
            Log.d("MyService", "startDownload executed")
        }

        fun getProgress(): Int {
            Log.d("MyService", "getProgress executed")
            return 0
        }

    }

    override fun onBind(intent: Intent): IBinder {
        return mBinder
    }
    ...
}

class MainActivity : AppCompatActivity() {

    lateinit var downloadBinder: MyService.DownloadBinder
    
    // 实现一个 connect，重写对应的方法，
    private val connection = object : ServiceConnection {
        // onServiceConnected()方法方法会在 Activity 与 Service 成功绑定的时候调用
        // 这里面会拿到 bind 方法返回的 binder
        override fun onServiceConnected(name: ComponentName, service: IBinder) {
            downloadBinder = service as MyService.DownloadBinder
            downloadBinder.startDownload()
            downloadBinder.getProgress()
        }
        
        // onServiceDisconnected()方法只有在 Service 的创建进程崩溃或者被杀掉的时候才会调用
        override fun onServiceDisconnected(name: ComponentName) {
        }

    }

    override fun onCreate(savedInstanceState: Bundle?) {
        ...
        bindServiceBtn.setOnClickListener {
            val intent = Intent(this, MyService::class.java)
            // BIND_AUTO_CREATE： 绑定后就创建, 这里我们不需要编写 service 的其余方法，
            // 因为我们操作主要是放在 binder 里面。
            bindService(intent, connection, Context.BIND_AUTO_CREATE) // 绑定 Service
        }
        unbindServiceBtn.setOnClickListener {
            unbindService(connection) // 解绑 Service
        }
    }

}
```

## Binder 一个服务的过程

1. 应用组件向 ActivityManagerService 发送一个绑定 Service 组件的进程间通信请求。
2. ActivityManagerService 发现用来运行 Service 组件的应用程序进程即为应用组件所运行在的应用程序进程，因此，它就直接通知该应用程序进程将 Service 组件启动起来。
3. Service 组件启动起来之后，ActivityManagerService 就请求它返回一个 Binder 本地对象，以便应用组件可以通过这个 Binder 本地对象来和 Service 组件建立连接。
4. ActivityManagerService 将前面从 Service 组件中获得的一个 Binder 本地对象发送给应用组件。
5. 应用组件获得了 ActivityManagerService 给它发送的 Binder 本地对象之后，就可以通过它来获得 Service 组件的一个访问接口。应用组件以后就可以通过这个访问接口来使用 Service 组件所提供的服务，这就相当于将 Service 组件绑定在应用组件内部了。

## Step1: bindService

调用 bindService 方法，传入的参数是 intent、一个 connection，以及 flag BIND_AUTO_CREATE。

```java
val intent = Intent(this, MyService::class.java)
bindService(intent, connection, Context.BIND_AUTO_CREATE) // 绑定 Service
```

---

## Step2: ContextWrapper.bindService

这一步直接转调 ContextImpl 的 bindService。

---

## Step3: ContextImpl.bindService

mPackageInfo 是一个 LoadedApk 类型，此处先调用其 getServiceDispatcher 方法，把用户传入的 connection 包装成一个 Binder 本地对象 sd。

getServiceDispatcher 传入的参数是用户定义的 connection，activity(getOuterContext), 主线程消息队列句柄(getHandler)。

再调用 ActivityManagerService 代理对象的成员函数 bindService 将前面获得的 Binder 本地对象 sd，以及 Intent 对象 service 等信息发送给 ActivityManagerService，以便 ActivityManagerService 可以将 Service 组件启动起来，并且将它连接到应用组件中。

```java
@Override
public boolean bindService(Intent service, ServiceConnection conn,
        int flags) {
    IServiceConnection sd;
    if (mPackageInfo != null) {
        sd = mPackageInfo.getServiceDispatcher(conn, getOuterContext(),
                mMainThread.getHandler(), flags);
    } else {
        throw new RuntimeException("Not supported in system context");
    }
    try {
        int res = ActivityManagerNative.getDefault().bindService(
            mMainThread.getApplicationThread(), getActivityToken(),
            service, service.resolveTypeIfNeeded(getContentResolver()),
            sd, flags);
        if (res < 0) {
            throw new SecurityException(
                    "Not allowed to bind to service " + service);
        }
        return res != 0;
    } catch (RemoteException e) {
        return false;
    }
}
```

我们细看一下 LoadedApk 的 getServiceDispatcher 方法的实现。

每一个 context 也就是 activity 都以自己为 key 在 LoadedApk 的 mServices 中维护了一个 map。这个 map 的 key 是用户提供的 connection，value 是 ServiceDispatcher。

在获取 ServiceDispatcher 的时候首先在 LoadedApk 类的成员变量 mServices 中检查是否存在一个以 ServiceConnection 对象 c 为关键字的 ServiceDispatcher 对象 sd。如果不存在，那么就会首先创建这个 ServiceDispatcher 对象 sd，接着再将它保存在以 Context 对象 context 为关键字的 HashMap 对象 map 中。如果以 Context 对象 context 为关键字的 HashMap 对象 map 不存在，那么就会先创建它，接着再将它保存在 LoadedApk 类的成员变量 mServices 中。

最后，调用前面所获得的 ServiceDispatcher 对象 sd 的成员函数 getIServiceConnection 来获得一个实现了 IServiceConnection 接口的 Binder 本地对象。
> IServiceConnection 返回的是一个 InnerConnection 对象，这个对象是一个 Binder 本地对象。提供了一个 connect 方法，来接受远程的消息。

```java
public final IServiceConnection getServiceDispatcher(ServiceConnection c,
        Context context, Handler handler, int flags) {
    synchronized (mServices) {
        LoadedApk.ServiceDispatcher sd = null;
        HashMap<ServiceConnection, LoadedApk.ServiceDispatcher> map = mServices.get(context);
        if (map != null) {
            sd = map.get(c);
        }
        if (sd == null) {
            sd = new ServiceDispatcher(c, context, handler, flags);
            if (map == null) {
                map = new HashMap<ServiceConnection, LoadedApk.ServiceDispatcher>();
                mServices.put(context, map);
            }
            map.put(c, sd);
        } else {
            sd.validate(context, handler);
        }
        return sd.getIServiceConnection();
    }
}

private static class InnerConnection extends IServiceConnection.Stub {
    final WeakReference<LoadedApk.ServiceDispatcher> mDispatcher;

    InnerConnection(LoadedApk.ServiceDispatcher sd) {
        mDispatcher = new WeakReference<LoadedApk.ServiceDispatcher>(sd);
    }

    public void connected(ComponentName name, IBinder service) throws RemoteException {
        LoadedApk.ServiceDispatcher sd = mDispatcher.get();
        if (sd != null) {
            sd.connected(name, service);
        }
    }
}
```

## Step4: ActivityManagerProxy.bindService

在应用进程获取到的 AMS 是一个远程代理对象，即 ActivityManagerProxy,随后触发它的 bindService 方法。

```java
public int bindService(IApplicationThread caller, IBinder token,
        Intent service, String resolvedType, IServiceConnection connection,
        int flags) throws RemoteException {
    Parcel data = Parcel.obtain();
    Parcel reply = Parcel.obtain();
    data.writeInterfaceToken(IActivityManager.descriptor);
    data.writeStrongBinder(caller != null ? caller.asBinder() : null);
    data.writeStrongBinder(token);
    service.writeToParcel(data, 0);
    data.writeString(resolvedType);
    data.writeStrongBinder(connection.asBinder());
    data.writeInt(flags);
    mRemote.transact(BIND_SERVICE_TRANSACTION, data, reply, 0);
    reply.readException();
    int res = reply.readInt();
    data.recycle();
    reply.recycle();
    return res;
}
```

## Step5: ActivityManagerService.bindService

根据参数 caller 来得到一个 ProcessRecord 对象 callerApp，用来描述正在请求 ActivityManagerService 执行绑定 Service 组件操作的一个 Activity 组件所运行在的应用程序进程。

根据参数 token 来得到一个 ActivityRecord 对象 activity，用来描述正在请求 ActivityManagerService 执行绑定 Service 组件操作的一个 Activity 组件。

```java
    public int bindService(IApplicationThread caller, IBinder token,
            Intent service, String resolvedType,
            IServiceConnection connection, int flags) {
        //...
        synchronized(this) {
            //...
            final ProcessRecord callerApp = getRecordForAppLocked(caller);
            //...

            ActivityRecord activity = null;
            if (token != null) {
                int aindex = mMainStack.indexOfTokenLocked(token);
                //...
                activity = (ActivityRecord)mMainStack.mHistory.get(aindex);
            }
            //...
            
            ServiceLookupResult res =
                retrieveServiceLocked(service, resolvedType,
                        Binder.getCallingPid(), Binder.getCallingUid());
            //...
            ServiceRecord s = res.record;
            //...
            AppBindRecord b = s.retrieveAppBindingLocked(service, callerApp);
            ConnectionRecord c = new ConnectionRecord(b, activity,
                    connection, flags, clientLabel, clientIntent);

            IBinder binder = connection.asBinder();
            ArrayList<ConnectionRecord> clist = s.connections.get(binder);
            if (clist == null) {
                clist = new ArrayList<ConnectionRecord>();
                s.connections.put(binder, clist);
            }
            clist.add(c);
            //...

            if ((flags&Context.BIND_AUTO_CREATE) != 0) {
                s.lastActivity = SystemClock.uptimeMillis();
                if (!bringUpServiceLocked(s, service.getFlags(), false)) {
                    return 0;
                }
            }
            //...
        }

        return 1;
    }
```

根据参数 service 来得到一个 ServiceRecord 对象 s，用来描述即将被绑定的 Service 组件。接着再调用 ServiceRecord 对象 s 的成员函数 retrieveAppBindingLocked 来得到一个 AppBindRecord 对象 b，表示 ServiceRecord 对象 s 所描述的 Service 组件是绑定在 ProcessRecord 对象 callerApp 所描述的一个应用程序进程中的。

```java
class ServiceRecord {
    public AppBindRecord retrieveAppBindingLocked(Intent intent,
            ProcessRecord app) {
        Intent.FilterComparison filter = new Intent.FilterComparison(intent);
        IntentBindRecord i = bindings.get(filter);
        if (i == null) {
            i = new IntentBindRecord(this, filter);
            bindings.put(filter, i);
        }
        AppBindRecord a = i.apps.get(app);
        if (a != null) {
            return a;
        }
        a = new AppBindRecord(this, i, app);
        i.apps.put(app, a);
        return a;
    }
}
```

接着将前面获得的 AppBindRecord 对象 b、ActivityRecord 对象 activity，以及参数 connection 封装成一个 ConnectionRecord 对象 c，表示 ActivityRecord 对象 activity 所描述的一个 Activity 组件通过参数 connection 绑定了 ServiceRecord 对象 s 所描述的一个 Service 组件，并且这个 Activity 组件是运行在 ProcessRecord 对象 callerApp 所描述的一个应用程序进程中的。

由于一个 Service 组件可能会被同一个应用程序进程中的多个 Activity 组件使用同一个 InnerConnection 对象来绑定，因此，在 ActivityManagerService 中，用来描述该 Service 组件的 ServiceRecord 对象就可能会对应有多个 ConnectionRecord 对象。在这种情况下，这些 ConnectionRecord 对象就会被保存在一个列表中。这个列表最终会被保存在对应的 ServiceRecord 对象的成员变量 connection 所描述的一个 HashMap 中，并且以它里面的 ConnectionRecord 对象共同使用的一个 InnerConnection 代理对象的 IBinder 接口为关键字。

> 这里想解释下什么叫 "一个 Service 组件被同一个应用进程中的多个 Activity 组件使用同一个 InnerConnection 对象来绑定"
> 前面可以知道，我们应用需要提供一个 connection，这个 connection 会在 LoadedApk 中被包装成 InnerConnection。
> ```java 
> public final IServiceConnection getServiceDispatcher(ServiceConnection c,
>        Context context, Handler handler, int flags) {
>    synchronized (mServices) {
>        LoadedApk.ServiceDispatcher sd = null;
>        HashMap<ServiceConnection, LoadedApk.ServiceDispatcher> map = mServices.get(context);
>        if (map != null) {
>            sd = map.get(c);
>        }
>        if (sd == null) {
>            sd = new ServiceDispatcher(c, context, handler, flags);
>            if (map == null) {
>                map = new HashMap<ServiceConnection, LoadedApk.ServiceDispatcher>();
>                mServices.put(context, map);
>            }
>            map.put(c, sd);
>        } else {
>            sd.validate(context, handler);
>        }
>        return sd.getIServiceConnection();
>    }
>}
>```
>
> 这里假设 ActivityA 先 bind 了目标服务，此时 mServices 中保存着对应的键值对。随后 ActivityB 使用同一个 connection 也来 bind，那此时 mServices.get(context) 拿到的 map 是 null 吗？
> 首先我们知道每一个 Activity 继承的 context 都是独自的实例，所以其不是同一个对象，但是 Context 重写了 hashCode 方法，使得同一个进程中 context 是逻辑上相等的。所以 ActivityB 会取出来 ActivityA 当时创建的 map，进而取得同一个 InnerConnection
> ```java
>  // contextimpl.java
>  public int hashCode() {
>      int result;
>      result = packageName.hashCode();
>      result = 31 * result + iconId;
>      return result;
>  }
>```
>


从前面的 Step1 可以知道，参数 flags 的 Context.BIND_AUTO_CREATE 位等于 1，因此，最后就会调用成员函数 bringUpServiceLocked 来启动 ServiceRecord 对象 s 所描述的一个 Service 组件。等到这个 Service 组件启动起来之后，ActivityManagerService 再将它与 ActivityRecord 对象 activity 所描述的一个 Activity 组件绑定起来。


## Step6: ActivityManagerService.bringUpServiceLocked




