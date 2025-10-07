#  应用程序的安装过程

Package 管理服务 PackageManagerService 在安装一个应用程序的过程中，会对这个应用程序的配置文件 AndroidManifest.xml 进行解析，以便可以获得它的安装信息。一个应用程序可以配置的安装信息很多，其中，最重要的就是它的组件信息，一个应用程序组件只有在配置文件中被正确地配置之后，才可以被 Activity 管理服务 ActivityManagerService 正常地启动起来。

Android 系统中的每一个应用程序都有一个 Linux 用户 ID。这些 Linux 用户 ID 就是由 Package 管理服务 PackageManagerService 来负责分配的。Package 管理服务 PackageManagerService 在安装一个应用程序时，如果发现它没有与其他应用程序共享同一个 Linux 用户 ID，那么就会为它分配一个唯一的 Linux 用户 ID，以便它可以在系统中获得合适的运行权限。

一个应用程序除了拥有一个 Linux 用户 ID 之外，还可以拥有若干个 Linux 用户组 ID，以便可以在系统中获得更多的资源访问权限，例如，读取联系人信息、使用摄像头、发送短信，以及拨打电话等权限。这些 Linux 用户组 ID 也是由 Package 管理服务 PackageManagerService 来负责分配的。Package 管理服务 PackageManagerService 在安装一个应用程序时，如果发现它申请了一个特定的资源访问权限，那么就会为它分配一个相应的 Linux 用户组 ID。


## PMS 启动逻辑

在 system 进程启动时候，会通过 PackageManagerService 的 main 方法将 PMS 服务启动起来。

### Step1: PackageManagerService.main

```java
public static final IPackageManager main(Context context, boolean factoryTest) {
    // 创建实例
    PackageManagerService m = new PackageManagerService(context, factoryTest);
    // 注册到 Service manager 中
    ServiceManager.addService("package", m);
    return m;
}
```

我们继续查看 PackageManagerService 的构造函数。

```java
    public PackageManagerService(Context context, boolean factoryTest) {
        //...
        // 用来管理应用程序的安装信息的。例如，用来管理 Package 管理服务 PackageManagerService 为应用程序分配的 Linux 用户 ID 和 Linux 用户组 ID。
        mSettings = new Settings();
        //...

        synchronized (mInstallLock) {
        synchronized (mPackages) {
            //...
            // 获取系统数据目录 `/data`
            File dataDir = Environment.getDataDirectory();
            //...
            // drm 应用私有数据目录 `/data/app-private`
            mDrmAppPrivateInstallDir = new File(dataDir, "app-private");

            //...
            /*
                由于 Android 系统每次启动时，都会重新安装一遍系统中的应用程序，但是有些应用程序信息每次安装都是需要保持一致的，
                例如，应用程序的 Linux 用户 ID；否则，应用程序每次在系统重新启动之后，表现可能都会不一致。因此，Package 管理服务
                PackageManagerService 每次在安装完成应用程序之后，都需要将它们的信息保存下来，以便下次安装时可以恢复回来。

                这里使用 readLP 来恢复安装信息。
            */
            mRestoredSettings = mSettings.readLP();
            //...
            // Find base frameworks (resource packages without code).
            //...
            // Environment.getRootDirectory() 获取的是 Android 系统目录 `/system`
            // mFrameworkDir 的目录是 `/system/framework`, 这里面保存的是资源型的应用程序，资源型的应用程序是用来打包资源文件的，它们不包含有执行代码。
            mFrameworkDir = new File(Environment.getRootDirectory(), "framework");
            //...
            // 安装保存在里面的应用程序
            scanDirLI(mFrameworkDir, PackageParser.PARSE_IS_SYSTEM
                    | PackageParser.PARSE_IS_SYSTEM_DIR,
                    scanMode | SCAN_NO_DEX, 0);
            
            // Collect all system packages.
            // 系统自带的应用程序
            mSystemAppDir = new File(Environment.getRootDirectory(), "app");
            //...
            scanDirLI(mSystemAppDir, PackageParser.PARSE_IS_SYSTEM
                    | PackageParser.PARSE_IS_SYSTEM_DIR, scanMode, 0);
            
            // Collect all vendor packages.
            // 设备厂商的应用程序
            mVendorAppDir = new File("/vendor/app");
            //...
            scanDirLI(mVendorAppDir, PackageParser.PARSE_IS_SYSTEM
                    | PackageParser.PARSE_IS_SYSTEM_DIR, scanMode, 0);
            //...
            // 用户自己安装应用的数据目录 `/data/app`
            mAppInstallDir = new File(dataDir, "app");
            //...
            scanDirLI(mAppInstallDir, 0, scanMode, 0);

            //...
            scanDirLI(mDrmAppPrivateInstallDir, PackageParser.PARSE_FORWARD_LOCK,
                    scanMode, 0);

            //...
            final boolean regrantPermissions = mSettings.mInternalSdkPlatform
                    != mSdkVersion;
            //...
            // 为申请了特定资源访问权限的应用程序分配响应的组 id
            updatePermissionsLP(null, null, true, regrantPermissions, regrantPermissions);
            // 把安装信息保存在配置文件，以便于下一次安装时恢复。
            mSettings.writeLP();

            //...
        } // synchronized (mPackages)
        } // synchronized (mInstallLock)
    }
```

### Step2: Settings.readLP

> [Android 共享用户 id](android/framework/app_framework/ref/shared_user.md)
> [Packages.xml 文件内容](android/framework/app_framework/ref/process_xml_content.md)
> [AndroidManifest 中 sharedUserID 的作用](android/framework/app_framework/ref/what_is_shared_user_id_in_android_manifest.md)
> [AndroidManifest sharedUserID 和 Package.xml 中 shared-user 标签的区别](android/framework/app_framework/ref/different_of_shareduseid_and_packages_xml.md)

```java
class Settings {
        // 这两个文件都是用来保存上一次的应用程序安装信息的，其中，后一个文件是用来备份前一个文件的。
        // `/data/system/packages.xml`
        private final File mSettingsFilename;
        // `/data/system/packages-backup.xml`
        private final File mBackupSettingsFilename;
        //...
        Settings() {
            File dataDir = Environment.getDataDirectory();
            File systemDir = new File(dataDir, "system");
            //...
            mSettingsFilename = new File(systemDir, "packages.xml");
            mBackupSettingsFilename = new File(systemDir, "packages-backup.xml");
            //...
        }
        boolean readLP() {
            FileInputStream str = null;
            if (mBackupSettingsFilename.exists()) {
                try {
                    str = new FileInputStream(mBackupSettingsFilename);
                    //...
                } catch (java.io.IOException e) {
                    // We'll try for the normal settings file.
                }
            }

            mPastSignatures.clear();

            try {
                if (str == null) {
                    //...
                    str = new FileInputStream(mSettingsFilename);
                }
                // 创建 xml 解析器
                XmlPullParser parser = Xml.newPullParser();
                parser.setInput(str, null);

                int type;
                //...

                int outerDepth = parser.getDepth();
                while ((type=parser.next()) != XmlPullParser.END_DOCUMENT
                       && (type != XmlPullParser.END_TAG
                               || parser.getDepth() > outerDepth)) {
                    //...

                    String tagName = parser.getName();
                    /*
                        package 标签值描述的是上一次安装的一个应用程序的信息
                    */
                    if (tagName.equals("package")) {
                        readPackageLP(parser);
                    } 
                    //...
                    /*
                        shared-user 标签值记录的是上一次安装时应用分配的共享用户 id。
                    */
                    else if (tagName.equals("shared-user")) {
                        readSharedUserLP(parser);
                    } 
                    //...

                str.close();

            } catch(XmlPullParserException e) {
                //...

            } catch(java.io.IOException e) {
                //...

            }

            //...

            return true;
            }
        }
}
```

### Step3: Settings.readPackageLP

```java
        //...
        private final ArrayList<PendingPackage> mPendingPackages
                = new ArrayList<PendingPackage>();
        //...
        private void readPackageLP(XmlPullParser parser)
                throws XmlPullParserException, IOException {
            String name = null;
            //...
            String idStr = null;
            String sharedIdStr = null;
            //...
            PackageSettingBase packageSetting = null;
            //...
            try {
                /*
                    标签值等于"package"的 xml 元素有三个属性 name、userId 和 sharedUserId，
                    其中，属性 name 用来描述上一次安装的一个应用程序的 Package 名称；
                    而属性 userId 和 sharedUserId 用来描述这个应用程序所使用的独立 Linux 用户 ID 和共享 Linux 用户 ID。
                */
                name = parser.getAttributeValue(null, "name");
                //...
                idStr = parser.getAttributeValue(null, "userId");
                //...
                sharedIdStr = parser.getAttributeValue(null, "sharedUserId");
                //...
                int userId = idStr != null ? Integer.parseInt(idStr) : 0;
                //...
                // 包名必须是存在的
                if (name == null) {
                    reportSettingsProblem(Log.WARN,
                            "Error in package manager settings: <package> has no name at "
                            + parser.getPositionDescription());
                } 
                //...
                else if (userId > 0) {
                    // 检查 Package 名称等于 name 的应用程序在上一次安装时是否被分配了一个独立的 Linux 用户 ID。
                    // 如果是，那么就会调用 Settings 类的成员函数 addPackageLP 将这个应用程序上一次安装时被分配的 Linux 用户 ID 保留下来。
                    packageSetting = addPackageLP(name.intern(), realName, new File(codePathStr),
                            new File(resourcePathStr), nativeLibraryPathStr, userId, versionCode,
                            pkgFlags);
                    //...
                } else if (sharedIdStr != null) {
                    /*
                        检查前面所获得的变量 sharedIdStr 的值是否不等于 null。如果不等于 null，那么就说明上一次安装 Package 名称等于 name 的应用程序时，
                        Package 管理服务 PackageManagerService 并没有给它分配一个独立的 Linux 用户 ID，而是让它与其他的应用程序共享同一个 Linux 用户 ID。

                        需要注意的是，这里并没有保留这个共享用户 id，而是构造了一个 PendingPackage。
                        why?
                        因为这个 id 不属于这个应用所有，而是属于一组应用的，需要等待后面解析完成 shared-user 信息后，再进行保留/设置。

                    */
                    userId = sharedIdStr != null
                            ? Integer.parseInt(sharedIdStr) : 0;
                    if (userId > 0) {
                        packageSetting = new PendingPackage(name.intern(), realName,
                                new File(codePathStr), new File(resourcePathStr),
                                nativeLibraryPathStr, userId, versionCode, pkgFlags);
                        //...
                        mPendingPackages.add((PendingPackage) packageSetting);
                        //...
                    } 
                    //...
                } 
                //...
            } catch (NumberFormatException e) {
                //...
            }
            
                //...
            }
```

### Step4: Settings.addPackageLP

```java
        // 每一个应用的安装信息都使用一个 PackageSetting 描述，这里使用 packageName 为 key 保存这些信息。
        private final HashMap<String, PackageSetting> mPackages =
                new HashMap<String, PackageSetting>();
        //...
        PackageSetting addPackageLP(String name, String realName, File codePath, File resourcePath,
                String nativeLibraryPathString, int uid, int vc, int pkgFlags) {
            PackageSetting p = mPackages.get(name);
            // 有记录，直接返回
            if (p != null) {
                if (p.userId == uid) {
                    return p;
                }
                // 如果 uid 和 原来的不一样，报错
                reportSettingsProblem(Log.ERROR,
                        "Adding duplicate package, keeping first: " + name);
                return null;
            }
            // 创建一个 PackageSetting
            p = new PackageSetting(name, realName, codePath, resourcePath, nativeLibraryPathString,
                    vc, pkgFlags);
            p.userId = uid;
            // 在系统中保留值为 uid 的 Linux 用户 ID
            if (addUserIdLP(uid, p, name)) {
                mPackages.put(name, p);
                return p;
            }
            return null;
        }
```

我们进一步分析下 addUserIdLP 的实现。

在 Android 系统中，大于或者等于 FIRST_APPLICATION_UID 并且小于(FIRST_APPLICATION_UID+MAX_APPLICATION_UIDS)的 Linux 用户 ID 是保留给应用程序使用的，而小于 FIRST_APPLICATION_UID 的 Linux 用户 ID 是保留给特权用户使用的。FIRST_APPLICATION_UID 和 MAX_APPLICATION_UIDS 的值分别定义为 10000 和 1000，从这里就可以看出，系统最多可以分配 1000 个 Linux 用户 ID 给应用程序使用。

虽然小于 FIRST_APPLICATION_UID 的 Linux 用户 ID 不能作为应用程序的 Linux 用户 ID，但是它们却可以以共享的方式被应用程序使用。例如，如果一个应用程序想要修改系统的时间，那么它就可以申请与名称为 "android.uid.system" 的特权用户共享同一个 Linux 用户 ID(1000)，即在配置文件中将它的 android：sharedUserId 属性值设置为 "android.uid.system"​。

```java
        private static final int FIRST_APPLICATION_UID =
            Process.FIRST_APPLICATION_UID;
        private static final int MAX_APPLICATION_UIDS = 1000;
        /*
            mUserIds 是一个类型为 ArrayList 的列表，用来维护那些已经分配给应用程序使用的 Linux 用户 ID，
            即大于或者等于 FIRST_APPLICATION_UID 的 Linux 用户 ID。如果保存在这个列表中的第 index 个位置的一个 Object 对象的值不等于 null，
            那么就说明值为(FIRST_APPLICATION_UID+index)的 Linux 用户 ID 已经被分配了。
        */
        private final ArrayList<Object> mUserIds = new ArrayList<Object>();
        /*
            mOtherUserIds 是一个类型为 SparseArray 的稀疏数组，用来维护那些已经分配给特权用户使用的 Linux 用户 ID，即小于 FIRST_APPLICATION_UID 的 Linux 用户 ID。
            如果一个小于 FIRST_APPLICATION_UID 的 Linux 用户 ID 已经被分配了，那么它在这个稀疏数组中所对应的一个 Object 对象的值就不等于 null。   
        */
        private final SparseArray<Object> mOtherUserIds =
                new SparseArray<Object>();
        private boolean addUserIdLP(int uid, Object obj, Object name) {
            // 非法 id
            if (uid >= FIRST_APPLICATION_UID + MAX_APPLICATION_UIDS) {
                return false;
            }
            // 三方应用 id，存储在 mUserIds 中
            if (uid >= FIRST_APPLICATION_UID) {
                int N = mUserIds.size();
                final int index = uid - FIRST_APPLICATION_UID;
                while (index >= N) {
                    mUserIds.add(null);
                    N++;
                }
                if (mUserIds.get(index) != null) {
                    reportSettingsProblem(Log.ERROR,
                            "Adding duplicate user id: " + uid
                            + " name=" + name);
                    return false;
                }
                mUserIds.set(index, obj);
            } else {
                // 系统应用 id
                if (mOtherUserIds.get(uid) != null) {
                    reportSettingsProblem(Log.ERROR,
                            "Adding duplicate shared id: " + uid
                            + " name=" + name);
                    return false;
                }
                mOtherUserIds.put(uid, obj);
            }
            return true;
        }
```

### Step5: Settings.readSharedUserLP

每一个标签值等于 "shared-user" 的 xml 元素都是用来描述上一次安装应用程序时所分配的一个共享 Linux 用户的。这个 xml 元素有三个属性 name、userId 和 system，其中，属性 name 和 userId 描述一个共享 Linux 用户的名称和 ID 值；而属性 system 用来描述这个共享 Linux 用户 ID 是分配给一个系统类型的应用程序使用的，还是分配给一个用户类型的应用程序使用的。

```java
        private void readSharedUserLP(XmlPullParser parser)
                throws XmlPullParserException, IOException {
            String name = null;
            String idStr = null;
            int pkgFlags = 0;
            SharedUserSetting su = null;
            try {
                // 读取 用户名 和 共享 id
                name = parser.getAttributeValue(null, "name");
                idStr = parser.getAttributeValue(null, "userId");
                int userId = idStr != null ? Integer.parseInt(idStr) : 0;
                // 是不是分配给系统类型应用
                if ("true".equals(parser.getAttributeValue(null, "system"))) {
                    pkgFlags |= ApplicationInfo.FLAG_SYSTEM;
                }
                if (name == null) { // 不会走到
                    //...
                } else if (userId == 0) { // 不会走到
                    //...
                } else {
                    // 保留共享用户 id
                    if ((su=addSharedUserLP(name.intern(), userId, pkgFlags)) == null) {
                        reportSettingsProblem(Log.ERROR,
                                "Occurred while parsing settings at "
                                + parser.getPositionDescription());
                    }
                }
            } catch (NumberFormatException e) {
                //...
            };
            //...
        }
```

### Step6: Settings.addSharedUserLP

```java
        // 每一个共享 Linux 用户都是使用一个 SharedUserSetting 对象来描述的。这些 SharedUserSetting 对象被保存在 Settings 类的成员变量 mSharedUsers 所描述的一个 HashMap 中，
        // 并且是以它们所描述的共享 Linux 用户的名称为关键字的。
        private final HashMap<String, SharedUserSetting> mSharedUsers =
                new HashMap<String, SharedUserSetting>();
        SharedUserSetting addSharedUserLP(String name, int uid, int pkgFlags) {
            SharedUserSetting s = mSharedUsers.get(name);
            if (s != null) {
                if (s.userId == uid) {
                    return s;
                }
                reportSettingsProblem(Log.ERROR,
                        "Adding duplicate shared user, keeping first: " + name);
                return null;
            }
            s = new SharedUserSetting(name, pkgFlags);
            s.userId = uid;
            // 这里为这些共享用户名分配用户 id
            if (addUserIdLP(uid, s, name)) {
                mSharedUsers.put(name, s);
                return s;
            }
            return null;
        }
```

在前面的 Step3 中提到，如果上一次安装的一个应用程序指定了要与其他应用程序共享同一个 Linux 用户 ID，那么 Package 管理服务 PackageManagerService 需要在解析完成上一次的应用程序安装信息中的共享 Linux 用户信息之后，再为它们保留它们上一次所使用的 Linux 用户 ID。这些未保留 Linux 用户 ID 的应用程序分别被封装成一个 PendingPackage 对象，并且保存在 Settings 类的成员变量 mPendingPackages 中。

现在我们已经设置好了共享用户名信息并给这些共享用户保留了 id，那此时我们就可以为之前需要共享 id 的应用保留 id 了。

```java
        public Object getUserIdLP(int uid) {
            if (uid >= FIRST_APPLICATION_UID) {
                int N = mUserIds.size();
                final int index = uid - FIRST_APPLICATION_UID;
                return index < N ? mUserIds.get(index) : null;
            } else {
                return mOtherUserIds.get(uid);
            }
        }

        boolean readLP() {
  //...     // 遍历 mPendingPackages
            int N = mPendingPackages.size();
            for (int i=0; i<N; i++) {
                final PendingPackage pp = mPendingPackages.get(i);
                // 获取之前创建好的 PackageSettings 对象
                Object idObj = getUserIdLP(pp.sharedId);
                // 如果有对应的信息，并且是一个 SharedUserSetting 实例，那就意味着这个共享用户 id 是可用的。
                if (idObj != null && idObj instanceof SharedUserSetting) {
                    // 创建对应的 PackageSetting 对象。
                    PackageSetting p = getPackageLP(pp.name, null, pp.realName,
                            (SharedUserSetting) idObj, pp.codePath, pp.resourcePath,
                            pp.nativeLibraryPathString, pp.versionCode, pp.pkgFlags, true, true);
                    //...
                    p.copyFrom(pp);
                } 
                //...
            }
            mPendingPackages.clear();

            //...

            return true;
        }
```

### Step7: PackageManagerService.scanDirLI

在上面，我们已经读取了所有的 package 信息，现在开始安装。

```java
    private void scanDirLI(File dir, int flags, int scanMode, long currentTime) {
        String[] files = dir.list();
        //...

        int i;
        // 遍历目录下面的文件
        for (i=0; i<files.length; i++) {
            File file = new File(dir, files[i]);
            // 判断是不是 apk 结尾的
            if (!isPackageFilename(files[i])) {
                // Ignore entries which are not apk's
                continue;
            }
            // 解析 apk 文件
            // 解析失败会返回 null 同时把 mLastScanError 设置成 INSTALL_FAILED_INVALID_APK
            PackageParser.Package pkg = scanPackageLI(file,
                    flags|PackageParser.PARSE_MUST_BE_APK, scanMode, currentTime);
            // Don't mess around with apps in system partition.
            if (pkg == null && (flags & PackageParser.PARSE_IS_SYSTEM) == 0 &&
                    mLastScanError == PackageManager.INSTALL_FAILED_INVALID_APK) {
                // Delete the apk
                Slog.w(TAG, "Cleaning up failed install of " + file);
                file.delete();
            }
        }
    }
```

### Step8: PackageManagerService.scanPackageLI

```java
    private PackageParser.Package scanPackageLI(File scanFile,
            int parseFlags, int scanMode, long currentTime) {
        //...
        String scanPath = scanFile.getPath();
        //...
        PackageParser pp = new PackageParser(scanPath);
        //...
        // 解析 apk
        final PackageParser.Package pkg = pp.parsePackage(scanFile,
                scanPath, mMetrics, parseFlags);
        //...
        // 安装 apk
        return scanPackageLI(pkg, parseFlags, scanMode | SCAN_UPDATE_SIGNATURE, currentTime);
    }
```

### Step9: PackageParser.parsePackage

这个函数没做太多的事情，就是读取出来 "AndroidManifest.xml"，随后使用重载版本 parsePackage 来进一步解析。

```java
    public Package parsePackage(File sourceFile, String destCodePath,
            DisplayMetrics metrics, int flags) {
        //...

        mArchiveSourcePath = sourceFile.getPath();
        //...

        XmlResourceParser parser = null;
        AssetManager assmgr = null;
        //...
        try {
            assmgr = new AssetManager();
            int cookie = assmgr.addAssetPath(mArchiveSourcePath);
            if(cookie != 0) {
                parser = assmgr.openXmlResourceParser(cookie, "AndroidManifest.xml");
                //...
            } 
            //...
        } catch (Exception e) {
            //...
        }
        //...
        String[] errorText = new String[1];
        Package pkg = null;
        //...
        try {
            // XXXX todo: need to figure out correct configuration.
            Resources res = new Resources(assmgr, metrics, null);
            pkg = parsePackage(res, parser, flags, errorText);
        } catch (Exception e) {
            //...
        }
        //...

        parser.close();
        assmgr.close();

        //...

        return pkg;
    }
```

另外一个重载版本的 parsePackage 实现如下。

```java
    private Package parsePackage(
        Resources res, XmlResourceParser parser, int flags, String[] outError)
        throws XmlPullParserException, IOException {
        AttributeSet attrs = parser;
        //...
        // 获取应用程序的包名称
        String pkgName = parsePackageName(parser, attrs, flags, outError);
        //...
        int type;
        // 使用这个包名称创建一个 Package 对象
        final Package pkg = new Package(pkgName);
        boolean foundApp = false;
        
        TypedArray sa = res.obtainAttributes(attrs,
                com.android.internal.R.styleable.AndroidManifest);
       //...
       // 读取 "android:sharedUserId" 属性的值，这个属性表示应用程序要与其他应用程序共享同一个 Linux 用户 ID
        String str = sa.getNonConfigurationString(
                com.android.internal.R.styleable.AndroidManifest_sharedUserId, 0);
        if (str != null && str.length() > 0) {
            //...
            pkg.mSharedUserId = str.intern();
           //...
        }
        sa.recycle();

        //...
        // 循环解析所有的标签
        while ((type=parser.next()) != parser.END_DOCUMENT
               && (type != parser.END_TAG || parser.getDepth() > outerDepth)) {
            //...

            String tagName = parser.getName();
            if (tagName.equals("application")) {
                //...
                // 使用 parseApplication 解析 application 标签
                if (!parseApplication(pkg, res, parser, attrs, flags, outError)) {
                    return null;
                }
            } 
            //...
            else if (tagName.equals("uses-permission")) {
                /*
                    uses-permission 标签对应一个资源访问权限。一个资源访问权限又是与一个 Linux 用户组 ID 相对应的，
                    即如果一个应用程序申请了某一个资源访问权限，那么它就会获得一个对应的 Linux 用户组 ID。
                */
                sa = res.obtainAttributes(attrs,
                        com.android.internal.R.styleable.AndroidManifestUsesPermission);

                // Note: don't allow this value to be a reference to a resource
                // that may change.
                // 获取权限的名字
                String name = sa.getNonResourceString(
                        com.android.internal.R.styleable.AndroidManifestUsesPermission_name);

                sa.recycle();

                if (name != null && !pkg.requestedPermissions.contains(name)) {
                    // 保存权限的名字
                    pkg.requestedPermissions.add(name.intern());
                }

                //...

            } //...

        return pkg;
        }
    }
```

### Step10: PackageParser.parseApplication

```java
    private boolean parseApplication(Package owner, Resources res,
            XmlPullParser parser, AttributeSet attrs, int flags, String[] outError)
        throws XmlPullParserException, IOException {
        //...
        int type;
        while ((type=parser.next()) != parser.END_DOCUMENT
               && (type != parser.END_TAG || parser.getDepth() > innerDepth)) {
            //...

            String tagName = parser.getName();
            // 解析 activity 组件
            if (tagName.equals("activity")) {
                Activity a = parseActivity(owner, res, parser, attrs, flags, outError, false);
                //...
                owner.activities.add(a);

            } else if (tagName.equals("receiver")) {
                // 解析 broadcast receiver 组件
                Activity a = parseActivity(owner, res, parser, attrs, flags, outError, true);
                //...

                owner.receivers.add(a);

            } else if (tagName.equals("service")) {
                // 解析 service
                Service s = parseService(owner, res, parser, attrs, flags, outError);
                //...

                owner.services.add(s);

            } else if (tagName.equals("provider")) {
                // 解析 content provider
                Provider p = parseProvider(owner, res, parser, attrs, flags, outError);
                //...

                owner.providers.add(p);

            } //...
        }

        return true;
    }
```

至此，我们就分析了当前文件的 AndroidManifest.xml 中的属性信息，随后回到 Step8 开始安装 APK。

### Step11: PackageManagerService.scanPackageLI 重载版本

首先我们来看下 PMS 类的几个数据成员。

```java
// 所有已经安装了的应用程序都是使用一个 Package 对象来描述的，这些 Package 对象以 Package 的名称为关键字保存在这个 hashMap 中。
final HashMap<String, PackageParser.Package> mPackages =
            new HashMap<String, PackageParser.Package>();
// All available activities, for your resolving pleasure.
final ActivityIntentResolver mActivities =
        new ActivityIntentResolver();

// All available receivers, for your resolving pleasure.
final ActivityIntentResolver mReceivers =
        new ActivityIntentResolver();

// All available services, for your resolving pleasure.
final ServiceIntentResolver mServices = new ServiceIntentResolver();

// Keys are String (provider class name), values are Provider.
final HashMap<ComponentName, PackageParser.Provider> mProvidersByComponent =
        new HashMap<ComponentName, PackageParser.Provider>();

// Mapping from provider base names (first directory in content URI codePath)
// to the provider information.
final HashMap<String, PackageParser.Provider> mProviders =
        new HashMap<String, PackageParser.Provider>();
```

然后，我们来分析这个重载版本的 scanPackageLI 方法。

这里主要是先对 Package 分配 UID，随后解析四大组件进行存储。


```java
    private PackageParser.Package scanPackageLI(PackageParser.Package pkg,
            int parseFlags, int scanMode, long currentTime) {
        //...

        SharedUserSetting suid = null;
        PackageSetting pkgSetting = null;

        //...
        
        synchronized (mPackages) {
            //...
            // 1. 为 Package 分配 Linux 用户 ID
            if (pkg.mSharedUserId != null) { // 如果 package 指定了 sharedUserID
                suid = mSettings.getSharedUserLP(pkg.mSharedUserId,  // 获取 sharedID
                        pkg.applicationInfo.flags, true);
                if (suid == null) {
                    //...
                    return null;
                }
                //...
            }

            //...
            pkgSetting = mSettings.getPackageLP(pkg, origPackage, realName, suid, destCodeFile,
                    destResourceFile, pkg.applicationInfo.nativeLibraryDir,
                    pkg.applicationInfo.flags, true, false);
            //...
        }    
        //...

        synchronized (mPackages) {
            //...
            // 把那个 package 保存在 mPackages 变量中
            mPackages.put(pkg.applicationInfo.packageName, pkg);
            //...

            int N = pkg.providers.size();
            StringBuilder r = null;
            int i;
            // 保存 contentProvider 信息
            for (i=0; i<N; i++) {
                PackageParser.Provider p = pkg.providers.get(i);
                //...
                mProvidersByComponent.put(new ComponentName(p.info.packageName,
                        p.info.name), p);
                //...
            }
            //...
            // 保存 service 信息
            N = pkg.services.size();
            r = null;
            for (i=0; i<N; i++) {
                PackageParser.Service s = pkg.services.get(i);
                //...
                mServices.addService(s);
                //...
            }
            //...
            // 保存 broadcast receiver 信息
            N = pkg.receivers.size();
            r = null;
            for (i=0; i<N; i++) {
                PackageParser.Activity a = pkg.receivers.get(i);
                //...
                mReceivers.addActivity(a, "receiver");
                //...
            }
            //...
            // 保存 activity 信息
            N = pkg.activities.size();
            r = null;
            for (i=0; i<N; i++) {
                PackageParser.Activity a = pkg.activities.get(i);
                //...
                mActivities.addActivity(a, "activity");
                //...
            }
            //...
        }

        return pkg;
    }
```

前面我们提到，在解析 packages.xml 文件的时候，对于 shared-user 标签，我们会把每个标签解析成一个 SharedUserSettings 对象，并以其 name 为关键字保存在 Settings 类的 mSharedUsers 对象中。

这里先分析 package 是不是指定了 sharedUserID，如果指定了，就调用 getSharedUserLP 尝试去获取 sharedUserID。

我们查看一下 `getSharedUserLP` 方法的实现。

```java
SharedUserSetting getSharedUserLP(String name,
        int pkgFlags, boolean create) {
    SharedUserSetting s = mSharedUsers.get(name);
    if (s == null) {
        // 不存在，尝试去创建
        if (!create) {
            return null;
        }
        s = new SharedUserSetting(name, pkgFlags);
        // private static final boolean MULTIPLE_APPLICATION_UIDS = true;
        if (MULTIPLE_APPLICATION_UIDS) {
            // 创建一个新的 uid
            s.userId = newUserIdLP(s);
        } else {
            /*
                public static final int FIRST_APPLICATION_UID = 10000;
                private static final int FIRST_APPLICATION_UID = Process.FIRST_APPLICATION_UID;
            */
            s.userId = FIRST_APPLICATION_UID;
        }
        Log.i(TAG, "New shared user " + name + ": id=" + s.userId);
        // < 0 means we couldn't assign a userid; fall out and return
        // s, which is currently null
        if (s.userId >= 0) {
            mSharedUsers.put(name, s);
        }
    }

    return s;
}
```

### Step12： Settings.getPackageLP

这个函数在当前时机，基本就是直接返回了，这里面核心的逻辑是在 Step6 的时候才会被直接触发。

```java
        private final HashMap<String, PackageSetting> mPackages =
                new HashMap<String, PackageSetting>();
        private PackageSetting getPackageLP(String name, PackageSetting origPackage,
                String realName, SharedUserSetting sharedUser, File codePath, File resourcePath,
                String nativeLibraryPathString, int vc, int pkgFlags, boolean create, boolean add) {
            PackageSetting p = mPackages.get(name);
            if (p != null) {
                //...
                // 理论上，在我现在的理解上，这个时机，这里不相等几乎是不可能的。
                // why?
                // 要么 mPackages 存放的是独立 用户 id 的应用，要么是来自于 mPendingPackages 转换过来的，它的 sharedUser 肯定是有的。
                // 难道是因为解析 package.xml 的时候的 sharedUser 和 AndroidManifest.xml 中的不一样吗？
                if (p.sharedUser != sharedUser) {
                    //...
                    p = null;
                } //...
            }
            // 什么时候这里会是 null 呢？ 还记得之前指定了 sharedUserID 的 package 会暂时被设置成 PendingPackage
            // 并存储在 mPendingPackages 中，在解析完 shared-user 的信息后，会遍历这个 mPendingPackages
            // 遍历的过程中，会调用这个 getPackageLP 方法 (Step6)。此时这个 p 就会是 null。
            if (p == null) {
                // Create a new PackageSettings entry. this can end up here because
                // of code path mismatch or user id mismatch of an updated system partition
                if (!create) {
                    return null;
                }
                if (origPackage != null) {
                    // We are consuming the data from an existing package.
                    p = new PackageSetting(origPackage.name, name, codePath, resourcePath,
                            nativeLibraryPathString, vc, pkgFlags);
                    //...
                    p.copyFrom(origPackage);
                    //...
                    p.sharedUser = origPackage.sharedUser;
                    p.userId = origPackage.userId;
                    p.origPackage = origPackage;
                    //...
                } else {
                    p = new PackageSetting(name, realName, codePath, resourcePath,
                            nativeLibraryPathString, vc, pkgFlags);
                   //...
                    p.sharedUser = sharedUser;
                    if (sharedUser != null) {
                        p.userId = sharedUser.userId;
                    } else if (MULTIPLE_APPLICATION_UIDS) {
                        // Clone the setting here for disabled system packages
                        PackageSetting dis = mDisabledSysPackages.get(name);
                        if (dis != null) {
                            //...
                            p.userId = dis.userId;
                            //...
                            addUserIdLP(p.userId, p, name);
                        } else {
                            // Assign new user id
                            p.userId = newUserIdLP(p); // 分配新的用户 id
                        }
                    } else {
                        p.userId = FIRST_APPLICATION_UID;
                    }
                }
                //...
                if (add) {
                    // Finish adding new package by adding it and updating shared
                    // user preferences
                    addPackageSettingLP(p, name, sharedUser);
                }
            }
            return p;
        }
```

### Step13: Settings.newUserIdLP

```java
// 正如前面描述的，mUserIds 保存这所有的已经分配的 Linux 用户 ID。
// 如果 id 已经分配了，那对应的 mUserIds[id] 不等于 null
private final ArrayList<Object> mUserIds = new ArrayList<Object>();
private int newUserIdLP(Object obj) {
    // Let's be stupidly inefficient for now...
    final int N = mUserIds.size();
    for (int i=0; i<N; i++) {
        if (mUserIds.get(i) == null) { // 找到一个不是 null 的，填充，返回。
            mUserIds.set(i, obj);
            return FIRST_APPLICATION_UID + i;
        }
    }

    // None left?
    if (N >= MAX_APPLICATION_UIDS) {
        return -1;
    }

    mUserIds.add(obj);
    return FIRST_APPLICATION_UID + N;
}
```

### Step14: PackageManagerService.updatePermissionsLP

> [PMS 设置的 uid 和 linux 如何同步呢?](android/framework/app_framework/ref/java_uid_and_linux_uid.md)

在上面执行完成后，就成功的安装了一个应用程序，在所有的应用程序安装完成后，PMS 就要来为前面所安装的应用程序分配 Linux 用户组 ID 了，即授予它们所申请的资源访问权限。

```java
    private void updatePermissionsLP(String changingPkg,
            PackageParser.Package pkgInfo, boolean grantPermissions,
            boolean replace, boolean replaceAll) {
        //...

        // Now update the permissions for all packages, in particular
        // replace the granted permissions of the system packages.
        if (grantPermissions) {
            // 遍历所有的存在 mPackages 中 pkg
            for (PackageParser.Package pkg : mPackages.values()) {
                if (pkg != pkgInfo) {
                    grantPermissionsLP(pkg, replaceAll);
                }
            }
        }
        
        //...
    }
```

### Step15: PackageManagerService.grantPermissionsLP

我们首先了解配置文件 AndroidManifest.xml 中的 uses-permission 标签和 Android 应用程序的 Linux 用户组 ID 的关系。

假设一个应用程序需要使用照相设备，那么它就需要在它的配置文件 AndroidManifest.xml 中添加下面这一行信息：

```xml
<uses-permission android:name="android.permission.CAMERA"/>
```

从前面的可以知道，Package 管理服务 PackageManagerService 在解析这个配置文件时，会将这个 uses-permission 标签中的 android：name 属性的值“android.permission.CAMERA”取出来，并且保存在一个对应的 Package 对象的成员变量 requestedPermissions 所描述的一个资源访问权限列表中。

Package 管理服务 PackageManagerService 在启动时，会调用 PackageManagerService 类的成员函数 readPermissions 来解析保存在设备上的/system/etc/permissions/platform.xml 文件中的内容。这个文件的内容是以 xml 格式保存的，里面包含了一系列的 permission 标签，用来描述系统中的资源访问权限列表，它们的格式如下所示。

```xml
<permission name="android.permission.CAMERA">
    <group gid="camera" />
</permission>
```

这个 permission 标签表示使用名称为“camera”的 Linux 用户组来描述名称为“android.permission.CAMERA”的资源访问权限。知道了一个 Linux 用户组的名称之后，我们就可以调用由 Linux 内核提供的函数 getgrnam 来获得对应的 Linux 用户组 ID，这样就可以将一个资源访问权限与一个 Linux 用户组 ID 关联起来。

Package 管理服务 PackageManagerService 会为这个文件中的每一个 permission 标签创建一个 BasePermission 对象，并且以这个标签中的 name 属性值作为关键字，将这些 BasePermission 对象保存在 PackageManagerService 类的成员变量 mSettings 所指向的一个 Settings 对象的成员变量 mPermissions 所描述的一个 HashMap 中。由于一个 permission 标签可以包含多个 group 子标签，即一个资源访问权限名称可以用来描述多个 Linux 用户组，因此，每一个 BasePermission 对象内部都有一个 gids 数组，用来保存所有与它对应的 Linux 用户组 ID。

在设备上的 /system/etc/permissions/platform.xml 文件中，还包含了一些全局的 group 标签。这些全局的 group 标签与 permission 标签是同一级的，用来描述系统中所有的应用程序默认都具有的资源访问权限。Package 管理服务 PackageManagerService 会将这些全局的 group 标签所描述的 Linux 用户组 ID 保存在 PackageManagerService 类的成员变量 mGlobalGids 所描述的一个数组中。


```java
    private void grantPermissionsLP(PackageParser.Package pkg, boolean replace) {
        // 读取安装包设置信息
        final PackageSetting ps = (PackageSetting)pkg.mExtras;
        //...
        // 是否要和其他应用共享同一个用户 ID
        final GrantedPermissions gp = ps.sharedUser != null ? ps.sharedUser : ps;
        //...

        if (replace) {
            //...
            if (gp == ps) {
                gp.grantedPermissions.clear();
                gp.gids = mGlobalGids;
            }
        }
        // 如果尚未分配用户组 id，那就用 global 的初始化
        if (gp.gids == null) {
            gp.gids = mGlobalGids;
        }

        final int N = pkg.requestedPermissions.size();
        for (int i=0; i<N; i++) {
            String name = pkg.requestedPermissions.get(i);
            BasePermission bp = mSettings.mPermissions.get(name);
            //...
            if (bp != null && bp.packageSetting != null) {
                final String perm = bp.name;
                boolean allowed;
                boolean allowedSig = false;
                if (bp.protectionLevel == PermissionInfo.PROTECTION_NORMAL
                        || bp.protectionLevel == PermissionInfo.PROTECTION_DANGEROUS) {
                    allowed = true;
                } else if (bp.packageSetting == null) {
                    // This permission is invalid; skip it.
                    allowed = false;
                } else if (bp.protectionLevel == PermissionInfo.PROTECTION_SIGNATURE
                        || bp.protectionLevel == PermissionInfo.PROTECTION_SIGNATURE_OR_SYSTEM) {
                    allowed = (checkSignaturesLP(
                            bp.packageSetting.signatures.mSignatures, pkg.mSignatures)
                                    == PackageManager.SIGNATURE_MATCH)
                            || (checkSignaturesLP(mPlatformPackage.mSignatures, pkg.mSignatures)
                                    == PackageManager.SIGNATURE_MATCH);
                    if (!allowed && bp.protectionLevel
                            == PermissionInfo.PROTECTION_SIGNATURE_OR_SYSTEM) {
                        if (isSystemApp(pkg)) {
                            // For updated system applications, the signatureOrSystem permission
                            // is granted only if it had been defined by the original application.
                            if (isUpdatedSystemApp(pkg)) {
                                PackageSetting sysPs = mSettings.getDisabledSystemPkg(
                                        pkg.packageName);
                                final GrantedPermissions origGp = sysPs.sharedUser != null
                                        ? sysPs.sharedUser : sysPs;
                                if (origGp.grantedPermissions.contains(perm)) {
                                    allowed = true;
                                } else {
                                    allowed = false;
                                }
                            } else {
                                allowed = true;
                            }
                        }
                    }
                    if (allowed) {
                        allowedSig = true;
                    }
                } else {
                    allowed = false;
                }
                if (false) {
                    if (gp != ps) {
                        Log.i(TAG, "Package " + pkg.packageName + " granting " + perm);
                    }
                }
                if (allowed) {
                    if ((ps.pkgFlags&ApplicationInfo.FLAG_SYSTEM) == 0
                            && ps.permissionsFixed) {
                        // If this is an existing, non-system package, then
                        // we can't add any new permissions to it.
                        if (!allowedSig && !gp.grantedPermissions.contains(perm)) {
                            allowed = false;
                            // Except...  if this is a permission that was added
                            // to the platform (note: need to only do this when
                            // updating the platform).
                            final int NP = PackageParser.NEW_PERMISSIONS.length;
                            for (int ip=0; ip<NP; ip++) {
                                final PackageParser.NewPermissionInfo npi
                                        = PackageParser.NEW_PERMISSIONS[ip];
                                if (npi.name.equals(perm)
                                        && pkg.applicationInfo.targetSdkVersion < npi.sdkVersion) {
                                    allowed = true;
                                    //...
                                    break;
                                }
                            }
                        }
                    }
                    if (allowed) {
                        // 增加用户组权限
                        if (!gp.grantedPermissions.contains(perm)) {
                            //...
                            gp.grantedPermissions.add(perm);
                            gp.gids = appendInts(gp.gids, bp.gids);
                        } else if (!ps.haveGids) {
                            gp.gids = appendInts(gp.gids, bp.gids);
                        }
                    } else {
                        //...
                    }
                } else {
                    if (gp.grantedPermissions.remove(perm)) {
                        //...
                        gp.gids = removeInts(gp.gids, bp.gids);
                        //...
                    } else {
                        //...
                    }
                }
            } else {
                //...
            }
        }

        if ((changedPermission || replace) && !ps.permissionsFixed &&
                ((ps.pkgFlags&ApplicationInfo.FLAG_SYSTEM) == 0) ||
                ((ps.pkgFlags & ApplicationInfo.FLAG_UPDATED_SYSTEM_APP) != 0)){
            // This is the first that we have heard about this package, so the
            // permissions we have now selected are fixed until explicitly
            // changed.
            ps.permissionsFixed = true;
        }
        ps.haveGids = true;
    }
```

### Step16: Settings.wirteLP

不分析了，累了，这一步就是把刚才解析出来的信息写入到 package.xml 文件中，为的是下一次重新使用。