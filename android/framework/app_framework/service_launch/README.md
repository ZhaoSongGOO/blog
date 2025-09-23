# Service 组件的启动

Service 组件是 Android 应用程序的四大组件之一，不过与 Activity 组件不一样，它主要用来处理与用户界面无关的业务逻辑。由于 Service 组件不直接与用户交互，因此，它涉及的业务逻辑一般都是计算型的，适合在后台运行。

与 Activity 组件的启动方式类似，Service 组件的启动方式也分为显式和隐式两种。对于隐式启动的 Service 组件来说，我们只需要知道它的组件名称；而对于显式启动的 Service 组件来说，我们需要知道它的类名称。

Service 组件可以被 Activity 组件启动，也可以被其他的 Service 组件启动。同时，它既可以在启动它的 Activity 组件或者 Service 组件所在的应用程序进程中启动，也可以在一个新的应用程序进程中启动。

当一个 Service 组件被一个 Activity 组件或者另外一个 Service 组件启动时，我们可以将它们绑定起来，以便启动者可以方便地得到它的访问接口。

## [Service 在独立进程中启动](android/framework/app_framework/service_launch/service__stanlone_process_launch.md)

## [Service 同进程中启动并使用 bind 创建长连接](android/framework/app_framework/service_launch/service_process_launch_and_bind.md)
