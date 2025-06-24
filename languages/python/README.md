# Python

## 如何构造一个只读又可扩展的类

### 背景

我现在在开发一个小工具，这个小工具类似于 make 一样会解析用户提供的 依赖描述文件来编排调度任务。

我当然没办法像 make 一样做的那么完整，所以这个依赖描述文件索性使用 python 文件来充数。下面展示了一个大概的依赖描述文件形式，本质为 python 文件。
```python
targetA = {
    "type":"a",
    "deps":["targetB"]
}

targetB = {
    "type":"b",
    "deps":[]
}
```

依赖文件解析的过程，也就直接使用 python 的 exec 方法来进行执行获取结果。就像下面这样，其中 env 是一注入到依赖文件的全局上下文，我们后续可以从 env 中读取到依赖文件执行完成的所有变量。

```python
with open("desc.file", "r") as f:
    env = {}
    exec(f.read(), env)
```

有时候，我还可以通过在 env 中预设变量，来让依赖描述文件中直接使用，例如：

```python
env = {
    "version": "0.1"
}
```

```python
targetA = {
    "type":f"a-{version}",
    "deps":["targetB"]
}
```

这样看起来一切都很好，但是随着工程的扩大，我可能存在多个不同的依赖描述文件，同时为了更好的管理，我提供了一个全局 env。这就会有一个问题，因为描述文件本身是一个 python 文件，用户自由度相当大，他极有可能在描述文件中对我全局的 env 的属性进行更改，这个 env 在被后续的依赖文件解析的时候，会出现莫名奇妙的问题。

```python
#
# env = {"version":"0.1"}
#
#
env = Env.getInstance() 

with open("desc1.file", "r") as f:
    exec(f.read(), env) # version = "0.2"

with open("desc2.file", "r") as f:
    exec(f.read(), env) # read version, result is "0.2", error!
```

所以我将这个 env 设置成一个只读的类，即描述文件中只可以读取它的属性，而不能进行修改。

### 具体设计

#### 只读的 Env
下面是这个只读类的具体设计，关键地方全部在注释中进行说明。

```python
import platform

def init_env_property_system():
    system = platform.system().lower()
    return system

def init_env_property_machine():
    machine = platform.machine().lower()
    return "x86_64" if machine == "amd64" else machine

# Env 类本身
class Env:
    def __init__(self):
        # 因为属性设置接口已经修改不可用，所以需要调用基类的属性设置接口进行属性初始化。
        super().__setattr__("system", init_env_property_system())
        super().__setattr__("machine", init_env_property_machine())

    # 重写属性设置接口，直接抛异常，避免属性设置。也可以采用更温和的手段，直接返回，反正不要直接修改属性就行了。
    def __setattr__(self, name, _):
        raise AttributeError(f"Can't set attribute \"{name}\". This is a read-only class.")
```

#### Env 扩展 EnvWrapper

EnvWrapper，这个类的作用是给 Env 提供一个扩展的能力，Env 可能包含的是最核心，最通用的全局属性或者方法，但是我们在某一次 exec 的时候，可能需要注入一些当前上下文需要的变量，EnvWrapper 会将当前上下文变量与 Env 本身组合暴露，而不污染 Env 本身。但是从用户来看，EnvWrapper 和 Env 是一样的使用方法。可以理解成这是一个装饰器模式，亦或是代理模式。

```python
class EnvWrapper:
    # wrapper 本身初始化会把 Env 设置成自己的属性。
    def __init__(self, env:Env):
        super().__setattr__("env", env)

    # 用户在获取wrapper的属性的时候，首先尝试从 Env 获取，没有在从自身属性获取。
    def __getattr__(self, item):
        try:
            return self.env.__getattribute__(item)
        except AttributeError as e:
            return self.__getattribute__(item)
    # 同样的，属性设置接口设置为不可用
    def __setattr__(self, name, _):
        raise AttributeError(f"Can't set attribute \"{name}\".. This is a read-only class.")

    # 扩展接口，这里用来把当前上下文比较关注的属性挂载在 wrapper 本身，而不是 env 上。
    def update(self, custom=None):
        if custom is None:
            custom = {}
        for key in custom.keys():
            super().__setattr__(key, custom[key])
        return self


# EnvBuild, 管理全局的 Env 对象单例
class EnvBuild:
    _env = None

    # 不考虑多线程安全问题，在 Env 对象没初始化的时候，进行初始化。
    @staticmethod
    def init_deps_env():
        if EnvBuild._env is None:
            EnvBuild._env = Env()
    
    # 对外的接口，可以使用 get_deps_env 在工具框架内部获取到 Env 单例，同时传入 custom 参数来扩展 env 属性。
    @staticmethod
    def get_deps_env(custom={}):
        EnvBuild.init_deps_env()
        return EnvWrapper(EnvBuild._env).update(custom)
```

#### 使用举例
```python
# 简单的使用方法
d = EnvBuild.get_deps_env({"age":100})
print(d.system, d.machine, d.age)
# error, throw exception
d.system = 12
```