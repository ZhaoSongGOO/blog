# ContentProvider 启动


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
        IContentProvider existing = getExistingProvider(context, name);
        if (existing != null) {
            return existing;
        }

        IActivityManager.ContentProviderHolder holder = null;
        try {
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

