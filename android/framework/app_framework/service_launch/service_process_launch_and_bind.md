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

首先获得 ServiceRecord 对象 r 所描述的 Service 组件的 android：process 属性，并且保存在变量 appName 中，接着根据这个属性的值，以及 ServiceRecord 对象 r 所描述的 Service 组件的用户 ID 在 ActivityManagerService 中查找是否已经存在一个对应的 ProcessRecord 对象 app。如果存在，那么就说明用来运行这个 Service 组件的应用程序进程已经存在了。因此，就会直接调用成员函数 realStartServiceLocked 在 ProcessRecord 对象 app 所描述的应用程序进程中启动这个 Service 组件。

```java
    private final boolean bringUpServiceLocked(ServiceRecord r,
            int intentFlags, boolean whileRestarting) { 
        //...
        
        final String appName = r.processName;
        ProcessRecord app = getProcessRecordLocked(appName, r.appInfo.uid);
        if (app != null && app.thread != null) {
            try {
                realStartServiceLocked(r, app);
                return true;
            } catch (RemoteException e) {
                Slog.w(TAG, "Exception when starting service " + r.shortName, e);
            }
        }
        //...
    }
```

## Step7: ActivityManagerService.realStartServiceLocked

首先将 ServiceRecord 对象 r 的成员变量 app 设置为 ProcessRecord 对象 app，接着又将 ServiceRecord 对象 r 添加到 ProcessRecord 对象 app 的成员变量 services 中，表示 ServiceRecord 对象 r 所描述的 Service 组件是在 ProcessRecord 对象 app 所描述的应用程序进程中启动的。

ProcessRecord 对象 app 的成员变量 thread 是一个类型为 ApplicationThreadProxy 的 Binder 代理对象，它指向了 ProcessRecord 对象 app 所描述的应用程序进程中的一个 ApplicationThread 对象。因此，就调用它的成员函数 scheduleCreateService 来请求 ProcessRecord 对象 app 所描述的应用程序进程将 ServiceRecord 对象 r 所描述的 Service 组件启动起来。

ServiceRecord 对象 r 所描述的 Service 组件启动完成之后，ActivityManagerService 就需要将它连接到请求绑定它的一个 Activity 组件中，这是通过调用 ActivityManagerService 类的另外一个成员函数 requestServiceBindingsLocked 来实现的。

```java
    private final void realStartServiceLocked(ServiceRecord r,
            ProcessRecord app) throws RemoteException {
        //...

        r.app = app;
        //...

        app.services.add(r);
        //...
        try {
            //...
            app.thread.scheduleCreateService(r, r.serviceInfo);
            //...
        } finally {
            //...
        }

        requestServiceBindingsLocked(r);
        
        //...
    }
```

---

## Step8: ApplicationThreadProxy.scheduleCreateService
## Step9: ApplicationThread.scheduleCreateService
## Step10: ActivityThread.queueOrSendMessage
## Step11: ActivityThread.H.handleMessage
## Step12: ActivityThread.handleCreateService
## Step13: MyService.onCreate

---

## Step14: ActivityManagerService.requestServiceBindingsLocked

在ServiceRecord对象r的成员变量bindings中，保存了一系列IntentBindRecord对象，每一个IntentBindRecord对象都用来描述若干个需要将ServiceRecord对象r所描述的Service组件绑定到它们里面去的应用程序进程。因此，while循环依次调用另外一个成员函数requestServiceBindingLocked将ServiceRecord对象r所描述的Service组件绑定到这些应用程序进程中。

```java
    private final void requestServiceBindingsLocked(ServiceRecord r) {
        Iterator<IntentBindRecord> bindings = r.bindings.values().iterator();
        while (bindings.hasNext()) {
            IntentBindRecord i = bindings.next();
            if (!requestServiceBindingLocked(r, i, false)) {
                break;
            }
        }
    }
```

参数rebind用来描述是否要将ServiceRecord对象r所描述的Service组件重新绑定到IntentBindRecord对象i所描述的应用程序进程中。从前面的调用过程可以知道，参数rebind的值为false，这意味着IntentBindRecord对象i所描述的应用程序进程是第一次请求绑定ServiceRecord对象r所描述的Service组件的。


```java
    private final boolean requestServiceBindingLocked(ServiceRecord r,
            IntentBindRecord i, boolean rebind) {
        //...
        if ((!i.requested || rebind) && i.apps.size() > 0) {
            try {
               //...
                r.app.thread.scheduleBindService(r, i.intent.getIntent(), rebind);
                if (!rebind) {
                    i.requested = true;
                }
                //...
            } catch (RemoteException e) {
                if (DEBUG_SERVICE) Slog.v(TAG, "Crashed while binding " + r);
                return false;
            }
        }
        return true;
    }
```

## Step15: ApplicationThreadProxy.scheduleBindService

传入的参数，token 是 ServiceRecord 本地对象，intent 是 service 要绑定的目标组件，rebind 代表是否重复绑定，在当前上下文中，是 false。

```java
    public final void scheduleBindService(IBinder token, Intent intent, boolean rebind)
            throws RemoteException {
        Parcel data = Parcel.obtain();
        data.writeInterfaceToken(IApplicationThread.descriptor);
        data.writeStrongBinder(token);
        intent.writeToParcel(data, 0);
        data.writeInt(rebind ? 1 : 0);
        mRemote.transact(SCHEDULE_BIND_SERVICE_TRANSACTION, data, null,
                IBinder.FLAG_ONEWAY);
        data.recycle();
    }
```

---

## Step16: ApplicationThread.scheduleBindService
## Step17: ActivityThread.queueOrSendMessage
## Step18: ActivityThread.H.handleMessage

---

## Step19: ActivityThread.handleBindService

这里首先从 mServices 中以 ServiceRecord 为 key 找到创建好的服务实例，随后调用其 onBind 方法获取 service 组件的本地 binder 对象，最终使用 AMS 的 publishService 远程调用返回数据。

```java
    private final void handleBindService(BindServiceData data) {
        Service s = mServices.get(data.token);
        if (s != null) {
            try {
                data.intent.setExtrasClassLoader(s.getClassLoader());
                try {
                    if (!data.rebind) {
                        IBinder binder = s.onBind(data.intent);
                        ActivityManagerNative.getDefault().publishService(
                                data.token, data.intent, binder);
                    } else {
                        s.onRebind(data.intent);
                        ActivityManagerNative.getDefault().serviceDoneExecuting(
                                data.token, 0, 0, 0);
                    }
                    ensureJitEnabled();
                } catch (RemoteException ex) {
                }
            } catch (Exception e) {
                if (!mInstrumentation.onException(s, e)) {
                    throw new RuntimeException(
                            "Unable to bind to service " + s
                            + " with " + data.intent + ": " + e.toString(), e);
                }
            }
        }
    }
```

## Step20: ActivityManagerService.publishService

参数token指向的是一个ServiceRecord对象，用来描述应用组件请求绑定的服务组件；参数intent指向的是一个Intent对象，应用组件最初就是通过它来请求ActivityManagerService绑定服务组件的；参数service指向的是服务组件内部的一个Binder本地对象。

每一个需要绑定ServiceRecord对象r所描述的Service组件的Activity组件都使用一个ConnectionRecord对象来描述。由于不同的Activity组件可能会使用相同的InnerConnection对象来绑定ServiceRecord对象r所描述的Service组件，因此，ActivityManagerService就会把这些使用了同一个InnerConnection对象的ConnectionRecord对象放在同一个列表中。这样ActivityManagerService就会得到与ServiceRecord对象r相关的一系列ConnectionRecord对象列表，它们最终保存在ServiceRecord对象r的成员变量connections所描述的一个HashMap中，并且以它们所使用的InnerConnection对象为关键字。

ConnectionRecord类的成员变量conn是一个类型为IServiceConnection的Binder代理对象，它引用了一个类型为InnerConnection的Binder本地对象。这个Binder本地对象是用来连接一个Service组件和一个Activity组件的，并且与这个Activity组件运行在同一个应用程序进程中。所以这里 conn.connected 本质是进行了一个远程调用。

```java
    public void publishService(IBinder token, Intent intent, IBinder service) {
        //...

        synchronized(this) {
            //...
            ServiceRecord r = (ServiceRecord)token;

            //...
            if (r != null) {
                Intent.FilterComparison filter
                        = new Intent.FilterComparison(intent);
                IntentBindRecord b = r.bindings.get(filter);
                if (b != null && !b.received) {
                    b.binder = service;
                    b.requested = true;
                    b.received = true;
                    if (r.connections.size() > 0) {
                        Iterator<ArrayList<ConnectionRecord>> it
                                = r.connections.values().iterator();
                        while (it.hasNext()) {
                            ArrayList<ConnectionRecord> clist = it.next();
                            for (int i=0; i<clist.size(); i++) {
                                ConnectionRecord c = clist.get(i);
                                if (!filter.equals(c.binding.intent.intent)) {
                                    if (DEBUG_SERVICE) Slog.v(
                                            TAG, "Not publishing to: " + c);
                                    if (DEBUG_SERVICE) Slog.v(
                                            TAG, "Bound intent: " + c.binding.intent.intent);
                                    if (DEBUG_SERVICE) Slog.v(
                                            TAG, "Published intent: " + intent);
                                    continue;
                                }
                                if (DEBUG_SERVICE) Slog.v(TAG, "Publishing to: " + c);
                                try {
                                    c.conn.connected(r.name, service);
                                } catch (Exception e) {
                                    Slog.w(TAG, "Failure sending service " + r.name +
                                          " to connection " + c.conn.asBinder() +
                                          " (in " + c.binding.client.processName + ")", e);
                                }
                            }
                        }
                    }
                }

                serviceDoneExecutingLocked(r, mStoppingServices.contains(r));

                Binder.restoreCallingIdentity(origId);
            }
        }
    }
```

## Step21: InnerConnection.connected

这个调用的是 ServiceDispatcher 的 connected 方法。

```java
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

## Step22: ServiceDispatcher.connected

ServiceDispatcher类的成员变量mActivityThread指向了ActivityThread类的成员变量mH，它是用来向应用程序Counter的主线程的消息队列发送消息的。

这里首先将参数name和service封装成一个RunConnection对象，然后再将这个RunConnection对象封装成一个消息，最后将这个消息发送到应用程序Counter的主线程的消息队列中。这个消息最终是在RunConnection类的成员函数run中处理的。

```java
    public void connected(ComponentName name, IBinder service) {
        if (mActivityThread != null) {
            mActivityThread.post(new RunConnection(name, service, 0));
        } else {
            doConnected(name, service);
        }
    }
```

## Step23: RunConnection.run

这里可以看到，run 方法里还是执行的外部类的 doConnected 方法。

```java
private final class RunConnection implements Runnable {
    RunConnection(ComponentName name, IBinder service, int command) {
        mName = name;
        mService = service;
        mCommand = command;
    }

    public void run() {
        if (mCommand == 0) {
            doConnected(mName, mService);
        } else if (mCommand == 1) {
            doDeath(mName, mService);
        }
    }

    final ComponentName mName;
    final IBinder mService;
    final int mCommand;
}
```

## Step24: ServiceDispatcher.doConnected

这个 mConnection 就是我们用户最初自己生成的 connection 对象，这里调用其回调函数 onServiceConnected 把 binder 对象传给他。

```java
public void doConnected(ComponentName name, IBinder service) {
    ServiceDispatcher.ConnectionInfo old;
    ServiceDispatcher.ConnectionInfo info;

    synchronized (this) {
    //...
    // If there is a new service, it is now connected.
    if (service != null) {
        mConnection.onServiceConnected(name, service);
    }
}
```


