# Service 在独立进程启动流程

本小节不仅描述了一个运行在独立进程服务的启动过程，同时也是对 start/stop 两个 api 使用以及隐式启动服务的流程分析。

Client 组件启动 Server 组件的过程如下所示。
1. Client 组件向 ActivityManagerService 发送一个启动 Server 组件的进程间通信请求。
2. ActivityManagerService 发现用来运行 Server 组件的应用程序进程不存在，因此，它就会首先将 Server 组件的信息保存下来，接着再创建一个新的应用程序进程。
3. 新的应用程序进程启动完成之后，就会向 ActivityManagerService 发送一个启动完成的进程间通信请求，以便 ActivityManagerService 可以继续执行启动 Server 组件的操作。
4. ActivityManagerService 将第 2 步保存下来的 Server 组件信息发送给第 2 步创建的应用程序进程，以便它可以将 Server 组件启动起来。

## Step1: ContextWrapper.startService

这里的 mBase 是注入的 `ContextImpl` 对象。

```java
@Override
public ComponentName startService(Intent service) {
    return mBase.startService(service);
}
```

## Step2: ContextImpl.startService

这里使用 getDefault 获取到 `ActivityManagerProxy` 对象，随后触发他的 startService 方法。

```java
@Override
public ComponentName startService(Intent service) {
    try {
        ComponentName cn = ActivityManagerNative.getDefault().startService(
            mMainThread.getApplicationThread(), service,
            service.resolveTypeIfNeeded(getContentResolver()));
        if (cn != null && cn.getPackageName().equals("!")) {
            throw new SecurityException(
                    "Not allowed to start service " + service
                    + " without permission " + cn.getClassName());
        }
        return cn;
    } catch (RemoteException e) {
        return null;
    }
}
```

## Step3: ActivityManagerProxy.startService

就是对 AMS 发送了一个类型为 START_SERVICE_TRANSACTION 的远程调用。

```java
public ComponentName startService(IApplicationThread caller, Intent service,
        String resolvedType) throws RemoteException
{
    Parcel data = Parcel.obtain();
    Parcel reply = Parcel.obtain();
    data.writeInterfaceToken(IActivityManager.descriptor);
    data.writeStrongBinder(caller != null ? caller.asBinder() : null);
    service.writeToParcel(data, 0);
    data.writeString(resolvedType);
    mRemote.transact(START_SERVICE_TRANSACTION, data, reply, 0);
    reply.readException();
    ComponentName res = ComponentName.readFromParcel(reply);
    data.recycle();
    reply.recycle();
    return res;
}
```

## Step4: ActivityManagerService.startService

啥也没干，使用 startServiceLocked 进一步处理请求。

```java
public ComponentName startService(IApplicationThread caller, Intent service,
        String resolvedType) {
    // Refuse possible leaked file descriptors
    if (service != null && service.hasFileDescriptors() == true) {
        throw new IllegalArgumentException("File descriptors passed in Intent");
    }

    synchronized(this) {
        final int callingPid = Binder.getCallingPid();
        final int callingUid = Binder.getCallingUid();
        final long origId = Binder.clearCallingIdentity();
        ComponentName res = startServiceLocked(caller, service,
                resolvedType, callingPid, callingUid);
        Binder.restoreCallingIdentity(origId);
        return res;
    }
}
```

## Step5: ActivityManagerService.startServiceLocked

在 ActivityManagerService 中，每一个 Service 组件都使用一个 ServiceRecord 对象来描述，就像每一个 Activity 组件都使用一个 ActivityRecord 对象来描述一样。

首先调用成员函数 retrieveServiceLocked 在 ActivityManagerService 中查找是否存在与参数 service 对应的一个 ServiceRecord 对象。如果不存在，那么 ActivityManagerService 就会到 PackageManagerService 中去获取与参数 service 对应的一个 Service 组件的信息，然后将这些信息封装成一个 ServiceRecord 对象，最后将这个 ServiceRecord 对象封装成一个 ServiceLookupResult 对象返回给调用者。

获得了与参数 service 对应的一个 ServiceRecord 对象 r 之后，接着就调用 ActivityManagerService 类的另外一个成员函数 bringUpServiceLocked 来启动 ServiceRecord 对象 r 所描述的一个 Service 组件，即 Server 组件。

```java
    ComponentName startServiceLocked(IApplicationThread caller,
            Intent service, String resolvedType,
            int callingPid, int callingUid) {
        synchronized(this) {
            //...

            ServiceLookupResult res =
                retrieveServiceLocked(service, resolvedType,
                        callingPid, callingUid);
            //...
            ServiceRecord r = res.record;
            //...
            if (!bringUpServiceLocked(r, service.getFlags(), false)) {
                return new ComponentName("!", "Service process is bad");
            }
            return r.name;
        }
    }
```

## Step6: ActivityManagerService.bringUpServiceLocked

首先获取 processName, 随后以这个名字查找是否存在一个已经存在的 ProcessRecord 对象 app。
如果 app 存在，就调用 realStartServiceLocked 去触发服务的启动。如果不存在就调用 startProcessLocked 启动对应的进程，并将 r 保存在 mPendingServices 中，表明待启动的服务。

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
                //...
            }
        }

        // Not running -- get it started, and enqueue this service record
        // to be executed when the app comes up.
        if (startProcessLocked(appName, r.appInfo, true, intentFlags,
                "service", r.name, false) == null) {
            //...
            return false;
        }
        
        if (!mPendingServices.contains(r)) {
            mPendingServices.add(r);
        }
        
        return true;
    }
```

---

## Step7: ActivityManagerService.startProcessLocked
## Step8: ActivityThread.main
## Step9: ActivityManagerProxy.attachApplication
## Step10: ActivityManagerService.attachApplication

---

## Step11: ActivityManagerService.attachApplicationLocked

参数 pid 指向的是前面所创建的应用程序进程的 PID。在前面的 Step7 中，ActivityManagerService 以这个 PID 为关键字将一个 ProcessRecord 对象保存在了成员变量 mPidsSelfLocked 中，因此，就可以通过参数 pid 将这个 ProcessRecord 对象取回来，并且保存在变量 app 中。

前面得到的 ProcessRecord 对象 app 就是用来描述新创建的应用程序进程的，现在既然这个应用程序进程已经启动起来了，就将它的成员变量 thread 设置为参数 thread 所指向的一个 ApplicationThread 代理对象，这样，ActivityManagerService 以后就可以通过这个 ApplicationThread 代理对象来和新创建的应用程序进程进行通信了。

然后检查位于 Activity 组件堆栈顶端的 Activity 组件是否需要在新创建的应用程序进程中启动。如果是，那么就会调用成员变量 mMainStack 的成员函数 realStartActivityLocked 将这个 Activity 组件启动起来。如果位于 Activity 组件堆栈顶端的 Activity 组件已经在新创建的应用程序进程中启动起来了，但是它的窗口没有显示出来，那么就会调用成员变量 mMainStack 的成员函数 ensureActivitiesVisibleLocked 把它的窗口显示出来。从这里就可以看出，当一个应用程序进程启动完成之后，ActivityManagerService 会优先处理需要在它里面启动或者显示的 Activity 组件，然后再处理需要在它里面启动的 Service 组件，这是因为 Activity 组件是需要与用户交互的，而 Service 组件则不需要。

最后检查保存在成员变量 mPendingServices 中的 Service 组件是否需要在新创建的应用程序进程中启动。如果需要，那么就首先将它从成员变量 mPendingServices 中删除，接着第再调用成员函数 realStartServiceLocked 将它启动起来。

```java
    private final boolean attachApplicationLocked(IApplicationThread thread,
            int pid) {
        ProcessRecord app;
        if (pid != MY_PID && pid >= 0) {
            synchronized (mPidsSelfLocked) {
                app = mPidsSelfLocked.get(pid);
            }
        } 
        //...

        String processName = app.processName;
        //...
        app.thread = thread;
        //...

        boolean badApp = false;
        //...

        // See if the top visible activity is waiting to run in this process...
        ActivityRecord hr = mMainStack.topRunningActivityLocked(null);
        if (hr != null && normalMode) {
            if (hr.app == null && app.info.uid == hr.info.applicationInfo.uid
                    && processName.equals(hr.processName)) {
                try {
                    if (mMainStack.realStartActivityLocked(hr, app, true, true)) {
                        didSomething = true;
                    }
                } catch (Exception e) {
                    Slog.w(TAG, "Exception in new application when starting activity "
                          + hr.intent.getComponent().flattenToShortString(), e);
                    badApp = true;
                }
            } else {
                mMainStack.ensureActivitiesVisibleLocked(hr, null, processName, 0);
            }
        }

        // Find any services that should be running in this process...
        if (!badApp && mPendingServices.size() > 0) {
            ServiceRecord sr = null;
            try {
                for (int i=0; i<mPendingServices.size(); i++) {
                    sr = mPendingServices.get(i);
                    if (app.info.uid != sr.appInfo.uid
                            || !processName.equals(sr.processName)) {
                        continue;
                    }

                    mPendingServices.remove(i);
                    i--;
                    realStartServiceLocked(sr, app);
                    didSomething = true;
                }
            } catch (Exception e) {
                //...
                badApp = true;
            }
        }
        //...

        return true;
    }
```

## Step12: ActivityManagerService.realStartServiceLocked

ProcessRecord 对象 app 的成员变量 thread 是一个类型为 ApplicationThreadProxy 的 Binder 代理对象，它指向了新创建的应用程序进程中的一个 ApplicationThread 对象。因此就可以调用它的成员函数 scheduleCreateService 来请求新创建的应用程序进程将 ServiceRecord 对象 r 所描述的 Service 组件启动起来。

```java
    private final void realStartServiceLocked(ServiceRecord r,
            ProcessRecord app) throws RemoteException {
        //...
        try {
            //...
            app.thread.scheduleCreateService(r, r.serviceInfo);
            //...
        } finally {
            //...
        }
        //...
    }
```

## Step13: ApplicationThreadProxy.scheduleCreateService

向远端的 ApplicationThread 对象发送了一个 SCHEDULE_CREATE_SERVICE_TRANSACTION 消息。

```java
    public final void scheduleCreateService(IBinder token, ServiceInfo info)
            throws RemoteException {
        Parcel data = Parcel.obtain();
        data.writeInterfaceToken(IApplicationThread.descriptor);
        data.writeStrongBinder(token);
        info.writeToParcel(data, 0);
        mRemote.transact(SCHEDULE_CREATE_SERVICE_TRANSACTION, data, null,
                IBinder.FLAG_ONEWAY);
        data.recycle();
    }
```

## Step14: ApplicationThread.scheduleCreateService

一样的，直接给 ActivityThread 的主线程发送了一个消息 CREATE_SERVICE。

```java
        public final void scheduleCreateService(IBinder token,
                ServiceInfo info) {
            CreateServiceData s = new CreateServiceData();
            s.token = token;
            s.info = info;

            queueOrSendMessage(H.CREATE_SERVICE, s);
        }
```

---

## Step15: ActivityThread.queueOrSendMessage

---

## Step16: ActivityThread.H.handleMessage

```java
case CREATE_SERVICE:
    handleCreateService((CreateServiceData)msg.obj);
    break;
```

## Step17: ActivityThread.handleCreateService

调用成员函数 getPackageInfoNoCheck 来获得一个用来描述即将要启动的 Service 组件所在的应用程序的 LoadedApk 对象，并且将它保存在变量 packageInfo 中。在前面提到，在进程中加载的每一个应用程序都使用一个 LoadedApk 对象来描述，通过它就可以访问到它所描述的应用程序的资源。

调用 LoadedApk 对象 packageInfo 的成员函数 getClassLoader 来获得一个类加载器，接着通过这个类加载器将 CreateServiceData 对象 data 所描述的一个 Service 组件加载到内存中，并且创建它的一个实例，保存在 Service 对象 service 中。由于 CreateServiceData 对象 data 所描述的 Service 组件即为应用程序中的 Server 组件，因此，Service 对象 service 指向的 Service 组件实际上是一个 Server 组件。然后创建和初始化了一个 ContextImpl 对象 context，用来作为前面所创建的 Service 对象 service 的运行上下文环境，通过它就可以访问到特定的应用程序资源，以及启动其他的应用程序组件。

然后创建了一个 Application 对象 app，用来描述 Service 对象 service 所属的应用程序。接着使用 Application 对象 app、ContextImpl 对象 context 和 CreateServiceData 对象 data 来初始化 Service 对象 service。

Service 对象 service 初始化完成之后，就会调用它的成员函数 onCreate，以便让它执行一些自定义的初始化工作。一般来说，我们在自定义一个 Service 组件时，都会重写其父类 Service 的成员函数 onCreate，以便可以执行一些业务相关的初始化工作。最后以 CreateServiceData 对象 data 的成员变量 token 为关键字，将 Service 对象 service 保存在 ActivityThread 类的成员变量 mServices 中。


```java
    private final void handleCreateService(CreateServiceData data) {
        //...

        LoadedApk packageInfo = getPackageInfoNoCheck(
                data.info.applicationInfo);
        Service service = null;
        try {
            java.lang.ClassLoader cl = packageInfo.getClassLoader();
            service = (Service) cl.loadClass(data.info.name).newInstance();
        } catch (Exception e) {
            //...
        }

        try {
            //...
            ContextImpl context = new ContextImpl();
            context.init(packageInfo, null, this);

            Application app = packageInfo.makeApplication(false, mInstrumentation);
            context.setOuterContext(service);
            service.attach(context, this, data.info.name, data.token, app,
                    ActivityManagerNative.getDefault());
            service.onCreate();
            mServices.put(data.token, service);
            try {
                ActivityManagerNative.getDefault().serviceDoneExecuting(
                        data.token, 0, 0, 0);
            } catch (RemoteException e) {
                // nothing to do.
            }
        } catch (Exception e) {
            //...
        }
    }
```
