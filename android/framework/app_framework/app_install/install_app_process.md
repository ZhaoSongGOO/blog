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
                    标签值等于“package”的 xml 元素有三个属性 name、userId 和 sharedUserId，
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
