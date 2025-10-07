# 应用程序的显示过程

Android 系统提供了一个默认的 Home 应用程序——Launcher，用来显示系统中已经安装了的应用程序，它是由 System 进程负责启动的，同时它也是系统中第一个启动的应用程序。

将系统中已经安装了的应用程序显示出来的目的是为了让用户有一个统一的入口来启动它们。一个根 Acitivity 组件的启动过程就代表了一个应用程序的启动过程。因此，应用程序 Launcher 在显示一个应用程序时，只需要获得它的根 Activity 组件信息即可。

一个应用程序的根 Activity 组件的类型被定义为 CATEGORY_LAUNCHER，同时它的 Action 名称被定义为 ACTION_MAIN，这样应用程序 Launcher 就可以通过这两个条件来请求 Package 管理服务 PackageManagerService 返回系统中所有已经安装了的应用程序的根 Activity 组件信息。

获得了系统中已经安装了的应用程序的根 Activity 组件信息之后，应用程序 Launcher 就会分别将它们封装成一个快捷图标，并且显示在系统的屏幕中，这样用户就可以通过点击这些快捷图标来启动相应的应用程序了。

System 进程是由 Zygote 进程负责启动的，而 System 进程在启动过程中，又会创建一个 ServerThread 线程来启动系统中的关键服务。当系统中的关键服务都启动起来之后，这个 ServerThread 线程就会通知 Activity 管理服务 ActivityManagerService 将应用程序 Launcher 启动起来。Launcher 启动的过程也就是应用程序桌面的显示过程。

## Step1: ServerThread.run

```java
    public void run() {
        //...

        Looper.prepare();

        //...

        // Critical services...
        try {
            //...
            context = ActivityManagerService.main(factoryTest);

            //...
            pm = PackageManagerService.main(context,
                    factoryTest != SystemServer.FACTORY_TEST_OFF);
            //...

        } catch (RuntimeException e) {
            //...
        }

        //...
        // 调用 AMS 的 systemReady 服务来通知 AMS 启动 launcher。
        // 这里 AMS 虽然使用 binder 获取，但是是一个本地 binder 对象。
        ((ActivityManagerService)ActivityManagerNative.getDefault())
                .systemReady(new Runnable() {
            public void run() {
                Slog.i(TAG, "Making services ready");

                //...
            }
        });
        //...

        Looper.loop();
        //...
    }
```

## Step2: ActivityManagerService.systemReady

这里使用 `mMainStack` 来启动 activity。 mMainStack 指向了一个 ActivityStack 对象，这个 ActivityStack 对象是用来描述系统的 Activity 组件堆栈的。

```java
    public void systemReady(final Runnable goingCallback) {
        //...
        {
            mMainStack.resumeTopActivityLocked(null);
        }
    }
```

## Step3: ActivityStack.resumeTopActivityLocked

这里如果发现没有 activity，就启动 launcher。

```java
    final boolean resumeTopActivityLocked(ActivityRecord prev) {
        // Find the first activity that is not finishing.
        ActivityRecord next = topRunningActivityLocked(null);
        //...
        if (next == null) {
            // There are no more activities!  Let's just start up the
            // Launcher...
            if (mMainStack) {
                // mService 指向 AMS 实例
                return mService.startHomeActivityLocked();
            }
        }
        //...
    }
```

## Step4: ActivityManagerService.startHomeActivityLocked

ActivityManagerService 类的成员变量 mFactoryTest 用来描述系统的运行模式。系统的运行模式有工厂测试模式和非工厂测试模式两种，其中，工厂测试模式又可以进一步划分为低级工厂测试模式和高级工厂测试模式两种。

当系统分别运行在非工厂测试模式、低级工厂测试模式和高级工厂测试模式时，ActivityManagerService 类的成员变量 mFactoryTest 的值就分别等于 SystemServer.FACTORY_TEST_OFF、SystemServer.FACTORY_TEST_LOW_LEVEL 和 SystemServer.FACTORY_TEST_HIGH_LEVEL。

ActivityManagerService 类的成员变量 mTopAction、mTopData 和 mTopComponent 是用来描述系统中第一个被启动的 Activity 组件的。

在非工厂测试模式和高级工厂测试模式中，成员变量 mTopAction 的值等于 Intent.ACTION_MAIN，而成员变量 mTopData 和 mTopComponent 的值均等于 null；

在低级工厂测试模式中，成员变量 mTopAction 和 mTopData 的值分别等于 Intent.ACTION_FACTORY_TEST 和 null，而成员变量 mTopComponent 用来描述一个 Action 名称等于 Intent.ACTION_FACTORY_TEST 的 Activity 组件的实现类名称。

通过设置这三个成员变量的值，我们就可以让系统在不同的运行模式中启动一个不同的首个应用程序，这样就可以方便测试系统的功能。

我们假设系统是运行在非工厂测试模式中的，即假设 ActivityManagerService 类的成员变量 mFactoryTest 的值等于 SystemServer.FACTORY_TEST_OFF。即一个 activity category 设置为 "android.intent.category.HOME"，name 为 "android.intent.action.MAIN"。

```xml
<activity
    android:name="com.android.launcher2.Launcher"
    android:launchMode="singleTask"
    android:clearTaskOnLaunch="true"
    android:stateNotNeeded="true"
    android:theme="@style/Theme"
    android:screenOrientation="nosensor"
    android:windowSoftInputMode="stateUnspecified|adjustPan">
    <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.HOME" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.MONKEY"/>
    </intent-filter>
</activity>
```

```java
    boolean startHomeActivityLocked() {
        //...
        Intent intent = new Intent(
            mTopAction,
            mTopData != null ? Uri.parse(mTopData) : null);
        intent.setComponent(mTopComponent);
        if (mFactoryTest != SystemServer.FACTORY_TEST_LOW_LEVEL) {
            intent.addCategory(Intent.CATEGORY_HOME);
        }
        // 从 PMS 中取出来对应的 Activity 信息
        ActivityInfo aInfo =
            intent.resolveActivityInfo(mContext.getPackageManager(),
                    STOCK_PM_FLAGS);
        if (aInfo != null) {
            intent.setComponent(new ComponentName(
                    aInfo.applicationInfo.packageName, aInfo.name));
            // Don't do this if the home app is currently being
            // instrumented.
            ProcessRecord app = getProcessRecordLocked(aInfo.processName,
                    aInfo.applicationInfo.uid);
            // 如果没有启动起来
            if (app == null || app.instrumentationClass == null) {
                intent.setFlags(intent.getFlags() | Intent.FLAG_ACTIVITY_NEW_TASK);
                mMainStack.startActivityLocked(null, intent, null, null, 0, aInfo,
                        null, null, 0, 0, 0, false, false);
            }
        } 
        return true;
    }
```

## Step5: ActivityStack.startActivityLocked

这个调用中，AMS 会请求 zygote 创建一个新的进程，并在进程启动后，启动对应的 activity (com.android.launcher2.Launcher)。并调用其 onCreate 方法。


## Step6: Launcher.onCreate

```java
    private Bundle mSavedState;
    //...
    private boolean mRestoring;
    //...
    private LauncherModel mModel;
    //...
    protected void onCreate(Bundle savedInstanceState) {
        //...
        LauncherApplication app = ((LauncherApplication)getApplication());
        mModel = app.setLauncher(this);
        //...
        setupViews();

        // 恢复状态数据
        mSavedState = savedInstanceState;
        restoreState(mSavedState);

        //...
        // mRestoring 为 false，表示 onCreata 需要马上加载系统中已经安装了的应用程序信息。
        if (!mRestoring) {
            mModel.startLoader(this, true);
        }

        //...
    }
```

## Step7: LauncherModel.startLoader

```java
    //...
    // 执行加载系统中已经安装了的应用程序的信息的操作，会放在 sWorkerThread 来执行。
    private LoaderTask mLoaderTask;
    //...
    private static final HandlerThread sWorkerThread = new HandlerThread("launcher-loader");
    static {
        sWorkerThread.start();
    }
    private static final Handler sWorker = new Handler(sWorkerThread.getLooper());
    //...
    public void startLoader(Context context, boolean isLaunching) {
        synchronized (mLock) {
            //...

            // Don't bother to start the thread if we know it's not going to do anything
            if (mCallbacks != null && mCallbacks.get() != null) {
                // If there is already one running, tell it to stop.
                LoaderTask oldTask = mLoaderTask;
                if (oldTask != null) {
                    if (oldTask.isLaunching()) {
                        // don't downgrade isLaunching if we're already running
                        isLaunching = true;
                    }
                    oldTask.stopLocked();
                }
                mLoaderTask = new LoaderTask(context, isLaunching);
                // 把任务抛到 sWorkerThread 的 looper 中执行。
                sWorker.post(mLoaderTask);
            }
        }
    }
```

## Step8: LoaderTask.run

应用程序 Launcher 按照工作区(workspace)的形式来显示系统中已经安装了的应用程序的快捷图标。每一个工作区都是用来描述一个抽象桌面的，它由 N 个屏幕组成。工作区中的每一个屏幕由 `X*Y` 个单元格组成。

屏幕中的每一个单元格用来显示一个应用程序快捷图标。用户可以设置当前要显示的屏幕，同时也可以将一个应用程序快捷图标从一个单元格移动到另外一个单元格。

```java
public void run() {
    //...
    final Callbacks cbk = mCallbacks.get();
    final boolean loadWorkspaceFirst = cbk != null ? (!cbk.isAllAppsVisible()) : true;

    // 标签语法，给循环取个名字，后面 break 可以直接从跳出这个块，避免大范围的 if else 嵌套。
    keep_running: {
        //...

        if (loadWorkspaceFirst) {
            //...
            loadAndBindWorkspace(); // 加载工作区
        } else {
            //...
            loadAndBindAllApps();  // 加载 app
        }

        if (mStopped) {
            break keep_running;
        }

        //...

        // second step
        if (loadWorkspaceFirst) {
            //...
            loadAndBindAllApps();
        } else {
            //...
            loadAndBindWorkspace();
        }
    }
    //...
}
```

## Step9: LoaderTask.loadAndBindAllApps

```java
private boolean mAllAppsLoaded;
private void loadAndBindAllApps() {
    //...
    // 检查 LauncherModel 类是否已经加载过系统中已经安装了的应用程序的信息, 如果加载过，那 mAllAppsLoaded 就是 true。
    if (!mAllAppsLoaded) {
        // 加载所有的信息，再显示。
        loadAllAppsByBatch();
        if (mStopped) {
            return;
        }
        mAllAppsLoaded = true;
    } else {
        // 加载过了，那就直接绑定一下就行了。
        onlyBindAllApps();
    }
}
```

## Step10: LoaderTask.loadAllAppsByBatch

```java
class LauncherModel {
    //...
    private int mBatchSize; // 0 is all apps at once
    //...
    // 在主线程创建，绑定的是主线程的 looper
    private DeferredHandler mHandler = new DeferredHandler();
    //...
    private AllAppsList mAllAppsList; // only access in worker thread
    //...

    class LoaderTask {
        //...
        private void loadAllAppsByBatch() {
            //...
            final Callbacks oldCallbacks = mCallbacks.get();
            //...
            // 创建一个 intent，这个 intent 的类型为 launcher，名称为 main，这其实就是 app 的启动 activity。
            final Intent mainIntent = new Intent(Intent.ACTION_MAIN, null);
            mainIntent.addCategory(Intent.CATEGORY_LAUNCHER);

            final PackageManager packageManager = mContext.getPackageManager();
            List<ResolveInfo> apps = null;

            int N = Integer.MAX_VALUE;

            int startIndex;
            int i=0;
            int batchSize = -1;
            while (i < N && !mStopped) {
                if (i == 0) {
                    // i==0， 意味着第一次进来，我们需要从 PMS 拿到这些应用信息。
                    mAllAppsList.clear();
                    //...
                    apps = packageManager.queryIntentActivities(mainIntent, 0);
                    //...
                    N = apps.size();
                    //...
                    // mBatchSize == 0, 说明需要一次性展示所有的应用
                    if (mBatchSize == 0) {
                        batchSize = N;
                    } else {
                        batchSize = mBatchSize;
                    }

                    //...
                    // 进行排序，按照这些 app 的名字从大到小的顺序排列
                    Collections.sort(apps,
                            new ResolveInfo.DisplayNameComparator(packageManager));
                    //...
                }

                //...
                for (int j=0; i<N && j<batchSize; j++) {
                    // This builds the icon bitmaps.
                    mAllAppsList.add(new ApplicationInfo(apps.get(i), mIconCache));
                    i++;
                }

                // 这里判断是不是第一批 activity，第一批就意味着 i 小于一个 batchSize。
                final boolean first = i <= batchSize;
                // 这个 callback 接口指向 LauncherActivity 组件。
                final Callbacks callbacks = tryGetCallbacks(oldCallbacks);
                final ArrayList<ApplicationInfo> added = mAllAppsList.added;
                mAllAppsList.added = new ArrayList<ApplicationInfo>();
                // 给主线程拋送任务
                mHandler.post(new Runnable() {
                    public void run() {
                        //...
                        if (callbacks != null) {
                            if (first) {
                                callbacks.bindAllApplications(added);
                            } else {
                                callbacks.bindAppsAdded(added);
                            }
                            //...
                        } else {
                            //...
                        }
                    }
                });

                //...
            }
            //...
        }
    }
}
```

## Step11: PackageManagerService.queryIntentActivities

```java
public List<ResolveInfo> queryIntentActivities(Intent intent,
        String resolvedType, int flags) {
    //...

    synchronized (mPackages) {
        String pkgName = intent.getPackage();
        // 从 mActivity 中过滤符合要求的 activity 即可
        if (pkgName == null) {
            return (List<ResolveInfo>)mActivities.queryIntent(intent,
                    resolvedType, flags);
        }
        //...
    }
}
```

## Step12: Launcher.bindAllApplications

Launcher 类的成员变量 mAllAppsGrid 指向了一个 AllApps2D 对象或者一个 AllApps3D 对象，这取决于 Launcher 组件采用的是 2D 界面还是 3D 界面。假设 Launcher 组件采用的是 2D 界面，那么调用 AllApps2D 类的成员函数 setApps 将保存在 ApplicationInfo 列表 apps 中的根 Activity 组件显示到屏幕上来。

```java
private AllAppsView mAllAppsGrid;
//...

private void setupViews() {
    //...
    mAllAppsGrid = (AllAppsView)dragLayer.findViewById(R.id.all_apps_view);
    //...
}
public void bindAllApplications(ArrayList<ApplicationInfo> apps) {
    mAllAppsGrid.setApps(apps);
}
```

## Step13: AllApps2D.setApps

```java
// AllApps2D 类的成员变量 mAllAppsList 用来保存所有需要在屏幕上显示的根 Activity 组件。
private ArrayList<ApplicationInfo> mAllAppsList = new ArrayList<ApplicationInfo>();
public void setApps(ArrayList<ApplicationInfo> list) {
    mAllAppsList.clear();
    addApps(list);
}

// 展示所有图标的视图组件
private GridView mGrid;

// 适配器，用来通知视图组件数据更新了
private AppsAdapter mAppsAdapter;

public void addApps(ArrayList<ApplicationInfo> list) {
//        Log.d(TAG, "addApps: " + list.size() + " apps: " + list.toString());

    final int N = list.size();

    for (int i=0; i<N; i++) {
        final ApplicationInfo item = list.get(i);
        int index = Collections.binarySearch(mAllAppsList, item,
                LauncherModel.APP_NAME_COMPARATOR);
        if (index < 0) {
            index = -(index+1);
        }
        mAllAppsList.add(index, item);
    }
    // 通知数据更新，以使得 GridView 渲染视图
    mAppsAdapter.notifyDataSetChanged();
}
```

## Step14: AllApps2D.onItemClick

我们的 GridView 设置了 item 点击响应为 AllApps2D，在点击一个图标后，就会调用 AllApps2D.onItemClick 方法。

```java
mGrid.setOnItemClickListener(this);
public void onItemClick(AdapterView parent, View v, int position, long id) {
    // 获取对应的 intent，然后 startActivity 启动。
    ApplicationInfo app = (ApplicationInfo) parent.getItemAtPosition(position);
    mLauncher.startActivitySafely(app.intent, app);
}
```
