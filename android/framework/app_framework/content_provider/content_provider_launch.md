# ContentProvider 启动

假设这样的一个场景，我们 client 访问某一个 provider，这个 provider 也是第一次被访问，其所在的进程还没有启动，大致分为下面几个部分。

1. client 组件通过 URI 来访问 provider 组件，以便可以获得它的博客文章条目的总数。
2. client 组件所运行在的应用程序进程发现它里面不存在一个用来访问对应 provider 组件的代理对象，于是，它就会通过 URI 来请求 ActivityManagerService 返回一个用来访问 provider 组件的代理对象。
3. ActivityManagerService 发现 provider 组件还没有启动起来，于是，它就会先创建一个新的应用程序进程，然后在这个新创建的应用程序进程中启动 provider 组件。
4. provider 组件启动起来之后，就会将自己发布到 ActivityManagerService 中，以便 ActivityManagerService 可以将它的一个代理对象返回给 client 组件使用。

## Step1: getContentResolver

```java
class ContextImpl extends Context {
    final void init(LoadedApk packageInfo,
            IBinder activityToken, ActivityThread mainThread,
            Resources container) {
        //...
        mMainThread = mainThread;
        mContentResolver = new ApplicationContentResolver(this, mainThread);

        setActivityToken(activityToken);
    }

    @Override
    public ContentResolver getContentResolver() {
        return mContentResolver;
    }
}
```

## Step2: contentResolver.acquireProvider

```java
class ContentResolver {
    //...
    public final IContentProvider acquireProvider(Uri uri) {
        // 检查参数 uri 所描述的 URI 是否以“content：//”开头。如果不是，那么就说明这个 URI 不是用来访问 ContentProvider 组件的，因此，就直接返回了。
        if (!SCHEME_CONTENT.equals(uri.getScheme())) {
            return null;
        }
        String auth = uri.getAuthority();
        if (auth != null) {
            return acquireProvider(mContext, uri.getAuthority());
        }
        return null;
    }
    //...
}

private static final class ApplicationContentResolver extends ContentResolver {
    public ApplicationContentResolver(Context context, ActivityThread mainThread) {
        super(context);
        mMainThread = mainThread;
    }

    @Override
    protected IContentProvider acquireProvider(Context context, String name) {
        return mMainThread.acquireProvider(context, name);
    }

    //...
}
```

## Step3: ActivityThread.acquireProvider

```java
    public final IContentProvider acquireProvider(Context c, String name) {
        IContentProvider provider = getProvider(c, name);
        if(provider == null)
            return null;
        //...
        return provider;
    }
```

## Step4: ActivityThread.getProvider

```java
    private final IContentProvider getExistingProvider(Context context, String name) {
        synchronized(mProviderMap) {
            final ProviderClientRecord pr = mProviderMap.get(name);
            if (pr != null) {
                return pr.mProvider;
            }
            return null;
        }
    }
    private final IContentProvider getProvider(Context context, String name) {
        // 尝试从缓存中获取数据
        IContentProvider existing = getExistingProvider(context, name);
        if (existing != null) {
            return existing;
        }

        IActivityManager.ContentProviderHolder holder = null;
        try {
            // 通过 AMS 获取数据
            holder = ActivityManagerNative.getDefault().getContentProvider(
                getApplicationThread(), name);
        } catch (RemoteException ex) {
        }
        if (holder == null) {
            Slog.e(TAG, "Failed to find provider info for " + name);
            return null;
        }

        IContentProvider prov = installProvider(context, holder.provider,
                holder.info, true);
        //...
        return prov;
    }
```

## Step5: ActivityManagerService.getContentProvider

```java
public final ContentProviderHolder getContentProvider(
        IApplicationThread caller, String name) {
    if (caller == null) {
        String msg = "null IApplicationThread when getting content provider "
                + name;
        Slog.w(TAG, msg);
        throw new SecurityException(msg);
    }

    return getContentProviderImpl(caller, name);
}
```

## Step6: ActivityManagerService.getContentProviderImpl

> Content Provider 组件还有另外一个重要的属性 android：multiprocess，如果它的值等于 true，那么就表示这个 Content Provider 组件可以在每一个访问它的应用程序进程中创建一个实例；
> 否则，这个 Content Provider 组件在整个系统中只能存在一个实例，并且这个实例是运行在一个独立的应用程序进程中的，其他应用程序只能通过 Binder 进程间通信机制来访问它。

```java
// ContentProviderRecord 是 ContentProviderHolder 的子类
private final ContentProviderHolder getContentProviderImpl(
    IApplicationThread caller, String name) {
    // 每一个已经启动的 provider 在 AMS 中都使用一个 ContentProviderRecord 对象来描述。
    /*
        ContentProviderRecord 对象分别保存在 ActivityManagerService 类的两个成员变量 mProvidersByName 和 mProvidersByClass 中。
        成员变量 mProvidersByName 所保存的 ContentProviderRecord 对象是以它们所对应的 ContentProvider 组件的 android：authorities 属性值为关键字的，
        而成员变量 mProvidersByClass 所保存的 ContentProviderRecord 对象是以它们所对应的 Content Provider 组件的类名为关键字的。
    */
    ContentProviderRecord cpr;
    ProviderInfo cpi = null;

    synchronized(this) {
        ProcessRecord r = null;
        if (caller != null) {
            // 通过传入的 caller 来获取调用方所在应用进程的 ProcessRecord 对象。
            r = getRecordForAppLocked(caller);
            //...
        }

        // First check if this content provider has been published...
        // 依据 authority 查找对应的 provider record 对象
        cpr = mProvidersByName.get(name);
        if (cpr != null) {
            //...
        } else {
            try {
                // 到 PackageManagerService 中去查找 android：authorities 属性值等于 name 的 ContentProvider 组件的信息，这些信息使用一个 ProviderInfo 对象 cpi 来描述。
                cpi = AppGlobals.getPackageManager().
                    resolveContentProvider(name,
                            STOCK_PM_FLAGS | PackageManager.GET_URI_PERMISSION_PATTERNS);
            } catch (RemoteException ex) {
            }
            //...
            /*
                ProviderInfo 对象 cpi 的成员变量 name 保存了它所描述的 Content Provider 组件的类名，接着在成员变量 mProvidersByClass 中检查是否存在与这个类名对应的一个 ContentProviderRecord 对象。
                如果不存在，那么就说明 android：authorities 属性值等于 name 的 Content Provider 组件还没有启动起来
            */
            cpr = mProvidersByClass.get(cpi.name);
            final boolean firstClass = cpr == null;
            if (firstClass) {
                try {
                    ApplicationInfo ai =
                        AppGlobals.getPackageManager().
                            getApplicationInfo(
                                    cpi.applicationInfo.packageName,
                                    STOCK_PM_FLAGS);
                    //...
                    cpr = new ContentProviderRecord(cpi, ai);
                } catch (RemoteException ex) {
                    // pm is in same process, this will never happen.
                }
            }

            // 检查是不是这个 provider 可以在调用进程实例化 (multiprocess=true)。如果可以的话，就直接返回这个 cpr
            // 以使得调用进程可以依据这个内容实例化自己的 provider 组件。
            if (r != null && cpr.canRunHere(r)) {
                // If this is a multiprocess provider, then just return its
                // info and allow the caller to instantiate it.  Only do
                // this if the provider is the same user as the caller's
                // process, or can run as root (so can be in any process).
                return cpr;
            }
            //...

            // This is single process, and our app is now connecting to it.
            // See if we are already in the process of launching this
            // provider.
            // mLaunchingProviders 中保存着所有正在启动 provider 组件
            final int N = mLaunchingProviders.size();
            int i;
            // 这里检查是不是当前的 provider 已经在启动中了
            for (i=0; i<N; i++) {
                if (mLaunchingProviders.get(i) == cpr) {
                    break;
                }
            }

            // If the provider is not already being launched, then get it
            // started.
            // 如果还没有启动。
            if (i >= N) {
                final long origId = Binder.clearCallingIdentity();
                // 创建一个新的应用进程
                ProcessRecord proc = startProcessLocked(cpi.processName,
                        cpr.appInfo, false, 0, "content provider",
                        new ComponentName(cpi.applicationInfo.packageName,
                                cpi.name), false);
                //...
                cpr.launchingApp = proc;
                mLaunchingProviders.add(cpr);
                Binder.restoreCallingIdentity(origId);
            }

            // Make sure the provider is published (the same provider class
            // may be published under multiple names).
            if (firstClass) {
                mProvidersByClass.put(cpi.name, cpr);
            }
            mProvidersByName.put(name, cpr);
            //...
        }
    }

    // Wait for the provider to be published...
    // ContentProviderRecord 对象 cpr 所描述的 Content Provider 组件启动完成，并且将它的一个代理对象传递给 ActivityManagerService。
    // 这里需要等 provider 运行进程启动成功，同时 provider 进程启动 对应的 provider。
    // 如果 provder 组件启动完成后，会触发 AMS，并将 cpr 的 provider 赋值为对应的组件。
    synchronized (cpr) {
        while (cpr.provider == null) {
            //...
            try {
                cpr.wait();
            } catch (InterruptedException ex) {
            }
        }
    }
    return cpr;
}
```

## Step7: ActivityManagerService.startProcessLocked

调用 Process 类的静态成员函数 start 来创建一个新的应用程序进程，并且将这个新创建的应用程序进程的入口设置为 ActivityThread 类的静态成员函数 main。

## Step8: ActivityThread.main

## Step9: ActivityManagerProxy.attachApplication

向 ActivityManagerService 发出一个类型为 ATTACH_APPLICATION_TRANSACTION 的进程间通信请求，以及将前面创建的一个 ApplicationThread 对象传递给 ActivityManagerService，以便 ActivityManagerService 可以和这个新创建的应用程序进程执行 Binder 进程间通信。

## Step10: ActivityManagerService.attachApplication

## Step11: ActivityManagerService.attachApplicationLocked

```java
   private final boolean attachApplicationLocked(IApplicationThread thread,
            int pid) {

        // Find the application record that is being attached...  either via
        // the pid if we are running in multiple processes, or just pull the
        // next app record if we are emulating process with anonymous threads.
        /*
            ActivityManagerService 以这个 PID 为关键字将一个 ProcessRecord 对象保存在了成员变量 mPidsSelfLocked 中，
            因此，就可以通过参数 pid 将这个 ProcessRecord 对象取回来，并且保存在变量 app 中。
        */
        ProcessRecord app;
        if (pid != MY_PID && pid >= 0) {
            synchronized (mPidsSelfLocked) {
                app = mPidsSelfLocked.get(pid);
            }
        } 
        //...
        app.thread = thread;
        //...

        boolean normalMode = mProcessesReady || isAllowedWhileBooting(app.info);
        // 调用成员函数 generateApplicationProvidersLocked 来获得需要在 ProcessRecord 对象 app 所描述的应用程序进程中启动的 Content Provider 组件
        List providers = normalMode ? generateApplicationProvidersLocked(app) : null;

       //...
        try {
            //...
            // 请求新创建的应用程序进程将这个列表中的 Content Provider 组件启动起来。
            thread.bindApplication(processName, app.instrumentationInfo != null
                    ? app.instrumentationInfo : app.info, providers,
                    app.instrumentationClass, app.instrumentationProfileFile,
                    app.instrumentationArguments, app.instrumentationWatcher, testMode, 
                    isRestrictedBackupMode || !normalMode,
                    mConfiguration, getCommonServicesLocked());
            //...
        } catch (Exception e) {
            //...
        }

        //...
        return true;
    }
```

## Step12: ApplicationThread.bindApplication

```java
public final void bindApplication(String processName,
        ApplicationInfo appInfo, List<ProviderInfo> providers,
        ComponentName instrumentationName, String profileFile,
        Bundle instrumentationArgs, IInstrumentationWatcher instrumentationWatcher,
        int debugMode, boolean isRestrictedBackupMode, Configuration config,
        Map<String, IBinder> services) {
    //...
    AppBindData data = new AppBindData();
    //...
    data.providers = providers;
    //...
    queueOrSendMessage(H.BIND_APPLICATION, data);
}
```

## Step13: ActivityThread.queueOrSendMessage

```java
private final void queueOrSendMessage(int what, Object obj, int arg1, int arg2) {
    synchronized (this) {
        if (DEBUG_MESSAGES) Slog.v(
            TAG, "SCHEDULE " + what + " " + mH.codeToString(what)
            + ": " + arg1 + " / " + obj);
        Message msg = Message.obtain();
        msg.what = what;
        msg.obj = obj;
        msg.arg1 = arg1;
        msg.arg2 = arg2;
        mH.sendMessage(msg);
    }
}
```

## Step14: ActivityThread.H.handleMessage

```java
//...
case BIND_APPLICATION:
    AppBindData data = (AppBindData)msg.obj;
    handleBindApplication(data);
    break;
//...
```

## Step15: ActivityThread.handleBindApplication

```java
private final void handleBindApplication(AppBindData data) {
    //...
    List<ProviderInfo> providers = data.providers;
    if (providers != null) {
        installContentProviders(app, providers);
        //...
    }

    //...
}
```

## Step16: ActivityThread.installContentProviders

```java
    private final void installContentProviders(
            Context context, List<ProviderInfo> providers) {
        final ArrayList<IActivityManager.ContentProviderHolder> results =
            new ArrayList<IActivityManager.ContentProviderHolder>();

        Iterator<ProviderInfo> i = providers.iterator();
        while (i.hasNext()) {
            ProviderInfo cpi = i.next();
            //...
            // 初始化对应的 provider 组件，返回的是这个组件的接口，这里应该是一个 binder 本地对象。
            IContentProvider cp = installProvider(context, null, cpi, false);
            if (cp != null) {
                IActivityManager.ContentProviderHolder cph =
                    new IActivityManager.ContentProviderHolder(cpi);
                cph.provider = cp;
                results.add(cph);
                // Don't ever unload this provider from the process.
                synchronized(mProviderMap) {
                    mProviderRefCountMap.put(cp.asBinder(), new ProviderRefCount(10000));
                }
            }
        }

        try {
            // 将所有启动的数据发送到 AMS 完成注册。
            ActivityManagerNative.getDefault().publishContentProviders(
                getApplicationThread(), results);
        } catch (RemoteException ex) {
        }
    }
```

## Step17: ActivityThread.installProvider

```java
    private final IContentProvider installProvider(Context context,
            IContentProvider provider, ProviderInfo info, boolean noisy) {
        ContentProvider localProvider = null;
        // provider 为 null，意味着需要再当前进程初始化对应的 provider 组件。
        if (provider == null) {
            //...
            Context c = null;
            ApplicationInfo ai = info.applicationInfo;
            if (context.getPackageName().equals(ai.packageName)) {
                c = context;
            } //...
            try {
                // info.name 是对应的 provider 组件的类名
                final java.lang.ClassLoader cl = c.getClassLoader();
                localProvider = (ContentProvider)cl.
                    loadClass(info.name).newInstance();
                // binder 本地对象
                provider = localProvider.getIContentProvider();
                //...
                // XXX Need to create the correct context for this provider.
                // 初始化 provider 组件，本质上就是去触发其 onCreate 方法。
                localProvider.attachInfo(c, info);
            } catch (java.lang.Exception e) {
                //...
            }
        } 

        //...

        synchronized (mProviderMap) {
            // Cache the pointer for the remote provider.
            String names[] = PATTERN_SEMICOLON.split(info.authority);
            for (int i=0; i<names.length; i++) {
                ProviderClientRecord pr = new ProviderClientRecord(names[i], provider,
                        localProvider);
                try {
                    //...
                    mProviderMap.put(names[i], pr);
                } catch (RemoteException e) {
                    return null;
                }
            }
            if (localProvider != null) { // 保存所有的本地 content provider 组件
                mLocalProviders.put(provider.asBinder(),
                        new ProviderClientRecord(null, provider, localProvider));
            }
        }
        return provider;
    }
```

## Step18: ActivityManagerService.publishContentProviders

这一步完成后，会导致上面 `Step6` 解释 while 循环，并返回到 `Step4`。返回之后会再一次调用 ActivityThread 的 installProvider 方法。

```java
    public final void publishContentProviders(IApplicationThread caller,
            List<ContentProviderHolder> providers) {
       //...
        synchronized(this) {
            final ProcessRecord r = getRecordForAppLocked(caller);
            //...

            final int N = providers.size();
            /*
                for 循环首先取出保存在参数 providers 中的每一个 ContentProviderHolder 对象 src，然后在 ActivityManagerService 中找到与它对应的一个 ContentProviderRecord 对象 dst，
                最后将 ContentProviderHolder 对象 src 所描述的一个 Content Provider 组件的一个 IContentProvider 访问接口保存在 ContentProviderRecord 对象 dst 的成员变量 provider 中          
            */
            for (int i=0; i<N; i++) {
                ContentProviderHolder src = providers.get(i);
                //...
                ContentProviderRecord dst = r.pubProviders.get(src.info.name);
                if (dst != null) {
                    //...

                    int NL = mLaunchingProviders.size();
                    int j;
                    for (j=0; j<NL; j++) {
                        if (mLaunchingProviders.get(j) == dst) {
                            mLaunchingProviders.remove(j);
                            j--;
                            NL--;
                        }
                    }
                    synchronized (dst) {
                        dst.provider = src.provider;
                        dst.app = r;
                        dst.notifyAll();
                    }
                    //...
                }
            }

            //...
        }
    }
```

## Step19: client 组件调用 ActivityThread.installProvider

这个场景下，传入的 provider 不是 null。

```java
    private final IContentProvider installProvider(Context context,
            IContentProvider provider, ProviderInfo info, boolean noisy) {
        ContentProvider localProvider = null;
        if (provider == null) {
            //...
        } 

        //...

        synchronized (mProviderMap) {
            // Cache the pointer for the remote provider.
            String names[] = PATTERN_SEMICOLON.split(info.authority);
            for (int i=0; i<names.length; i++) {
                ProviderClientRecord pr = new ProviderClientRecord(names[i], provider,
                        localProvider);
                try {
                    provider.asBinder().linkToDeath(pr, 0);
                    mProviderMap.put(names[i], pr);
                } catch (RemoteException e) {
                    return null;
                }
            }
            //...
        }

        return provider;
    }
```
