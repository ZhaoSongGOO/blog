# MVC、MVP、MVVM

## MVC

1. 经典MVC（Smalltalk-80原始定义）
- 观察者模式驱动
在原始MVC设计中，View直接监听Model的变化（通过观察者模式），无需Controller介入数据更新。

<img src="android/interview/mvc/resources/mvc_1.png" style="width:70%">

- Controller的作用
仅处理用户输入事件（如点击、键盘操作），不参与数据更新流程。

2. Web MVC框架的实践（如Spring MVC）
- 完全隔离的View-Model
View 仅通过Controller传递的Model数据进行渲染，无直接访问权。

<img src="android/interview/mvc/resources/mvc_2.png" style="width:70%">

- View不持有Model引用
每次请求均为独立数据副本，避免直接操作业务模型。

## MVP

MVP的目标：彻底消除View与Model的关联，强制所有逻辑集中于Presenter。就类似于上面提到的完全隔离的 View-Model.

<img src="android/interview/mvc/resources/mvp_1.png" style="width:70%">

## MVVM

MVP 在 Presenter 中编写的业务逻辑和 UI 更新逻辑大量混合在一块。为了降低这种更新逻辑的重复编写，借助于底层的数据绑定能力，便提出了 MVVM 模式，即 Model-View-ViewModel 模式。

和 MVP 相比就是把 UI 更新的逻辑交由底层数据绑定引擎来实现。

<img src="android/interview/mvc/resources/mvvm_1.png" style="width:70%">

- Model 逻辑

```javascript
// 用户数据模型（纯数据对象）
class UserModel {
  constructor() {
    this.users = []; // 模拟数据库存储
  }

  // 保存用户数据（模拟异步操作）
  saveUser(name, email) {
    return new Promise((resolve) => {
      setTimeout(() => {
        this.users.push({ name, email });
        resolve(true); // 返回操作结果
      }, 1000);
    });
  }
}
```

- View 逻辑

```html
<!-- 视图模板（HTML/XAML） -->
<div class="form">
  <!-- 双向绑定到ViewModel属性 -->
  <input type="text" 
         bind:value="userName" 
         placeholder="请输入姓名" />
  
  <input type="email" 
         bind:value="userEmail" 
         placeholder="请输入邮箱" />

  <!-- 显示错误信息（单向绑定） -->
  <div class="error" if:visible="errorMessage">
    {{ errorMessage }}
  </div>

  <!-- 绑定命令和按钮状态 -->
  <button bind:command="submitCommand" 
          bind:disabled="isLoading">
    {{ isLoading ? '提交中...' : '立即注册' }}
  </button>

  <!-- 加载动画（单向绑定） -->
  <div class="spinner" if:visible="isLoading"></div>
</div>
```

- ViewModel 层

```javascript
// ViewModel类（核心逻辑层）
class UserViewModel {
  constructor(model) {
    this.model = model;
    
    // 可观察属性（自动触发视图更新）
    this.userName = "";     // 双向绑定到输入框
    this.userEmail = "";    // 双向绑定到输入框
    this.isLoading = false; // 单向绑定到加载动画
    this.errorMessage = ""; // 单向绑定到错误提示

    // 命令对象（绑定到按钮点击）
    this.submitCommand = {
      execute: () => this.handleSubmit()
    };
  }

  // 处理表单提交
  async handleSubmit() {
    this.isLoading = true;
    this.errorMessage = "";

    try {
      // 数据验证
      if (!this.userName || !this.userEmail) {
        throw new Error("所有字段必须填写");
      }

      // 调用Model保存数据
      const success = await this.model.saveUser(this.userName, this.userEmail);
      
      if (success) {
        // 清空表单
        this.userName = "";
        this.userEmail = "";
      }
    } catch (error) {
      this.errorMessage = error.message;
    } finally {
      this.isLoading = false;
    }
  }
}
```

