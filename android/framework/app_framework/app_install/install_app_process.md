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