# binder

## 简介

binder进程间通信机制是在Openbinder的基础上实现的[插图]，它采用CS通信方式，其中，提供服务的进程称为Server进程，而访问服务的进程称为Client进程。同一个Server进程可以同时运行多个组件来向Client进程提供服务，这些组件称为Service组件[插图]。同时，同一个Client进程也可以同时向多个Service组件请求服务，每一个请求都对应有一个Client组件，或者称为Service代理对象。binder进程间通信机制的每一个Server进程和Client进程都维护一个binder线程池来处理进程间的通信请求，因此，Server进程和Client进程可以并发地提供和访问服务。

Server进程和Client进程的通信要依靠运行在内核空间的binder驱动程序来进行。binder驱动程序向用户空间暴露了一个设备文件/dev/binder，使得应用程序进程可以间接地通过它来建立通信通道。Service组件在启动时，会将自己注册到一个Service Manager组件中，以便Client组件可以通过ServiceManager组件找到它。因此，我们将Service Manager组件称为binder进程间通信机制的上下文管理者，同时由于它也需要与普通的Server进程和Client进程通信，我们也将它看作是一个Service组件，只不过它是一个特殊的Service组件。

<img src="android/framework/binder/resources/1.png" style="width:80%">

从图可以看出，Client、Service和Service Manager运行在用户空间，而binder驱动程序运行在内核空间，其中，Service Manager和binder驱动程序由系统负责提供，而Client和Service组件由应用程序来实现。Client、Service和Service Manager均是通过系统调用open、mmap和ioctl来访问设备文件/dev/binder，从而实现与binder驱动程序的交互，而交互的目的就是为了能够间接地执行进程间通信。

## 基础数据结构

### binder_work

描述一个待处理的工作项, 其中 entry 是一个双向链表的结构，用来将 binder_work 组织起来成一个链表。type 表示工作项的类型。

```c

struct list_head {
	struct list_head *next, *prev;
};

struct binder_work {
	struct list_head entry;
	enum {
		BINDER_WORK_TRANSACTION = 1, // 有新的 binder 事务（RPC 调用）需要处理。
		BINDER_WORK_TRANSACTION_COMPLETE, // 事务处理完成，需要通知对方。
		BINDER_WORK_NODE, // 节点相关的管理操作（比如引用计数）。
		BINDER_WORK_DEAD_BINDER, // binder 对象死亡，需要通知注册了死亡回调的进程。
		BINDER_WORK_DEAD_BINDER_AND_CLEAR, // 对象死亡并且需要清理相关资源。
		BINDER_WORK_CLEAR_DEATH_NOTIFICATION, // 需要清除死亡通知。
	} type;
};
```

这里我有两个疑问，第一这个 list_head 结构是如何实现双向链表的，第二既然这个 binder_work 可以代表这么多情况，但是看起来内容很简单，如何承载更多的信息呢？

先回答第一个问题，list_head 是 linux 内核中使用非常普遍的双向链表管理结构，在使用的过程中牵扯到一个宏 container_of.

我们先举个例子：

```c
// 初始化链表头
struct list_head list;
// INIT_LIST_HEAD(&list);
list.next = &list;
list.prec = &list;

struct binder_work work{.type=BINDER_WORK_TRANSACTION};

list_add(&work->entry, &list);

// 遍历

struct binder_work *node;
list_for_each_entry(node, &list, entry){
	printk("type=%d", node->type);
}

```

首先我们初始化一个链表头，这个头的 next 和 prev 都指向自己。随后我们构造自己的 binder_node, 并通过 list_add 来将 binder_node 添加到链表中，其实只是将 binder_node 的 entry 添加到链表中。list_add 实现如下,就是个简单的双向链表头插法。

```c
static inline void __list_add(struct list_head *new,
			      struct list_head *prev,
			      struct list_head *next)
{
	next->prev = new;
	new->next = next;
	new->prev = prev;
	prev->next = new;
}

static inline void list_add(struct list_head *new, struct list_head *head)
{
	__list_add(new, head, head->next);
}
```

随后我们可能会在需要的时候进行遍历，在遍历的过程中，声明一个目标类型的指针，用来承载迭代过程中的目标对象，然后这个 list_for_each_entry 使用起来很神奇，第一个参数是我们刚声明的指针，第二个参数是链表地址，第三个参数是list_head 在你的结构里面的字段名，例如对于 binder_node 来说，就是 entry。可以看到这个宏展开后就是个 for(x;y;z) 的结构。

- 使用 list_entry 来获取 entry 只想的 biner_work 节点，并返回地址到 pos。
- prefetch 不需要关注，这个是一个优化，即将内容优先加载到 L1 缓存中。
- pos->next 进入下一个节点。

这里最有意思的就是这个 list_entry, 可以看到他接受的是 list_head 指针、binder_work 类型参数、list_head 指针在 binder_work 结构中对应的结构名 entry.

随后 list_entry 直接转调 container_of 宏，这个宏只做了:

<img src="android/framework/binder/resources/2.png" style="width:20%">

- 将 list_head 地址类型关联到 binder_work->entry。方便后续进行指针计算。
- 使用 offset 获取 entry 字段在 binder_work 中的地址偏移。随后使用 list_head 指针减去 这个偏移量就是 binder_work 的地址。

更有意思的是为了获取 offset，是先将地址 0 转换成 binder_work 指针类型，随后获取成员地址，那这样这个成员的地址其实就是偏移。需要注意的是，这里是获取成员地址操作，这是一个编译期逻辑，而不是空指针访问数据，空指针访问会触发段错误。如何区分是获取成员地址还是空指针访问，我理解区别就在于有没有声明对应的类型指针，声明了就是空指针访问，否则就是获取地址操作。


```c
// linux/stddef.h
#define offsetof(TYPE, MEMBER) ((size_t) &((TYPE *)0)->MEMBER)

// linux/kernel.h
#define container_of(ptr, type, member) ({			\
	const typeof( ((type *)0)->member ) *ç = (ptr);	\
	(type *)( (char *)__mptr - offsetof(type,member) );})

// linux/list.h
#define list_entry(ptr, type, member) \
	container_of(ptr, type, member)

/**
 * list_for_each_entry	-	iterate over list of given type
 * @pos:	the type * to use as a loop cursor.
 * @head:	the head for your list.
 * @member:	the name of the list_struct within the struct.
 */
#define list_for_each_entry(pos, head, member)				\
	for (pos = list_entry((head)->next, typeof(*pos), member);	\
	     prefetch(pos->member.next), &pos->member != (head); 	\
	     pos = list_entry(pos->member.next, typeof(*pos), member))
```
然后是第二个问题，这么简单的一个结构体是如何承载不同 binder 工作项的信息的。

其实这个 binder_work 只是一个"基类" 或者说标识，它用来在真正的 binder_work_xxx 中只是一个成员。

例如 binder_transaction 这个子类。

```c
struct binder_transaction {
    struct binder_work work;   // 头部，嵌入了 binder_work
    // 下面是事务的详细内容
    struct binder_process *from;
    struct binder_thread *from_thread;
    struct binder_transaction *to_parent;
    struct binder_transaction *to_child;
    struct binder_node *to_node;
    struct binder_buffer *buffer;
    unsigned int code;
    unsigned int flags;
    // ... 还有很多其他事务相关字段
};
```

### binder_node

代表一个 server 组件的实体对象，每当一个进程（比如 SystemServer）把某个 binder 服务注册到 binder 驱动时，驱动就会为这个服务分配一个 `binder_node` 结构体,就像 SystemService 进程一样，一个进程可能提供了多个服务，每一个服务都对应着一个 binder_node。

```c
struct binder_node {
	int debug_id;
	struct binder_work work;
	union {
		struct rb_node rb_node;
		struct hlist_node dead_node;
	};
	struct binder_proc *proc;
	struct hlist_head refs;
	int internal_strong_refs;
	int local_weak_refs;
	int local_strong_refs;
	void __user *ptr;
	void __user *cookie;
	unsigned has_strong_ref : 1;
	unsigned pending_strong_ref : 1;
	unsigned has_weak_ref : 1;
	unsigned pending_weak_ref : 1;
	unsigned has_async_transaction : 1;
	unsigned accept_fds : 1;
	int min_priority : 8;
	struct list_head async_todo;
};
```
1. **rb_node**
每个进程（`binder_proc`）可能会注册/持有多个 binder 实体对象（比如一个进程可以有多个 binder 服务）。为了高效管理这些对象，binder 驱动在每个 `binder_proc` 里，用**红黑树（rbtree）**来存储和查找它所拥有的所有 `binder_node`，每个 binder_node 以 rb_node 的形式称为红黑树的节点。至于如何通过 rb_node 定位到 binder_node 呢？ 那就还是之前提到的 container_of 宏。

2. **proc**

proc 成员是一个 binder_proc 类型，指向的是提供该 binder_node 的进程实体，也就是说，`node->proc` 让你知道“这个 binder 服务是哪个进程拥有的”。

3. **refs**

一个binder实体对象可能会同时被多个Client组件引用，因此，binder驱动程序就使用结构体binder_ref来描述这些引用关系，并且将引用了同一个binder实体对象的所有引用都保存在一个hash列表中。这个hash列表通过binder实体对象的成员变量refs来描述，而binder驱动程序通过这个成员变量就可以知道有哪些Client组件引用了同一个binder实体对象。

4. **local_strong_refs, internal_strong_refs, local_weak_refs**

这三个成员从名字可以看出用来记录不同来源对于该 binder_node 的引用状态，从而控制其生命周期。

- internal_strong_refs:统计binder 驱动内部（比如 binder_ref 结构体）对该 binder_node 的强引用数量。主要来自于其他进程通过 handle 强引用该 binder 服务对象时，binder 驱动会增加 internal_strong_refs。

- local_strong_refs: 统计宿主进程内部对该 binder_node 的强引用数量。当宿主进程内部有 Java 层强引用（比如 ServiceManager 持有某个 Service 的 Ibinder 对象），会增加 local_strong_refs。

- local_weak_refs: 统计宿主进程内部对该 binder_node 的弱引用数量。弱引用不会阻止对象被销毁，只是用来判断“有没有人在关注这个对象”。

5. **ptr, cookie**

ptr 和 cookie 指向两个用户空间的地址，其中，成员变量cookie指向该Service组件的地址，而成员变量ptr指向该Service组件内部的一个引用计数对象（类型为weakref_impl）的地址。

6. **has_async_transaction**

这个字段来表明当前 binder_node 即 server 组件是不是正在处理异步事务。一般情况下，binder驱动程序都是将一个事务保存在一个线程的一个todo队列中的，表示要由该线程来处理该事务。每一个事务都关联着一个binder实体对象，表示该事务的目标处理对象，即要求与该binder实体对象对应的Service组件在指定的线程中处理该事务。然而，当binder驱动程序发现一个事务是异步事务时，就会将它保存在目标binder实体对象的一个异步事务队列中，这个异步事务队列就是由该目标binder实体对象的成员变量async_todo来描述的。异步事务的定义是那些单向的进程间通信请求，即不需要等待应答的进程间通信请求，与此相对的便是同步事务。因为不需要等待应答，binder驱动程序就认为异步事务的优先级低于同步事务，具体就表现为在同一时刻，一个binder实体对象的所有异步事务至多只有一个会得到处理，其余的都等待在异步事务队列中，而同步事务就没有这个限制。

7. **work**

binder_node 中有一个 binder_work 成员 work，就如刚才说的，binder_work 代表一个事务，那 node 为什么要持有 work 呢？主要目的是进行生命周期同步，当一个binder实体对象的引用计数由0变成1，或者由1变成0时，binder驱动程序就会请求相应的Service组件增加或者减少其引用计数。这时候binder驱动程序就会将该引用计数修改操作封装成一个类型为binder_node的工作项，即将一个binder实体对象的成员变量work的值设置为BINDER_WORK_NODE，并且将它添加到相应进程的todo队列中去等待处理。

8. **min_priority**

用来描述 binder 服务执行服务逻辑所在线程的线程优先级。

9. **accept_fds**

accept_fds 用于标记该 binder 服务对象是否允许接收文件描述符。- 在 binder 跨进程通信过程中，除了普通的数据，还可以通过 binder 机制传递文件描述符（比如 socket、文件、管道等）。但有些 binder 服务出于安全或设计考虑，不希望/不允许接收 FD，以防止资源泄漏或被攻击。 这时，`accept_fds` 就作为一个开关来控制：

- 1/true：允许通过 binder 传递 FD 给该服务对象。
- 0/false：不允许通过 binder 传递 FD，驱动会拒绝或丢弃这类请求。

### binder_ref_death

```c
struct binder_ref_death {
	struct binder_work work;
	void __user *cookie;
};
```

结构体binder_ref_death用来描述一个Service组件的死亡接收通知。在正常情况下，一个Service组件被其他Client进程引用时，它是不可以销毁的。然而，Client进程是无法控制它所引用的Service组件的生命周期的，因为Service组件所在的进程可能会意外地崩溃，从而导致它意外地死亡。一个折中的处理办法是，Client进程能够在它所引用的Service组件死亡时获得通知，以便可以做出相应的处理。这时候Client进程就需要将一个用来接收死亡通知的对象的地址注册到binder驱动程序中。

成员变量cookie用来保存负责接收死亡通知的对象的地址，成员变量work的取值为BINDER_WORK_DEAD_BINDER、BINDER_WORK_CLEAR_DEATH_NOTIFICATION或者BINDER_WORK_DEAD_BINDER_AND_CLEAR，用来标志一个具体的死亡通知类型。

binder驱动程序决定要向一个Client进程发送一个Service组件死亡通知时，会将一个binder_ref_death结构体封装成一个工作项，并且根据实际情况来设置该结构体的成员变量work的值，最后将这个工作项添加到Client进程的todo队列中去等待处理。

什么时候会发送死亡通知呢?

client 在注册了死亡监听后，binder 驱动会在下面两种场景发送死亡通知。

- 当binder驱动程序监测到一个Service组件死亡时，它就会找到该Service组件对应的binder实体对象，然后通过binder实体对象的成员变量refs就可以找到所有引用了它的Client进程，最后就找到这些Client进程所注册的死亡接收通知，即一个binder_ref_death结构体。这时候binder驱动程序就会将该binder_ref_death结构体添加到Client进程的todo队列中去等待处理。在这种情况下，binder驱动程序将死亡通知的类型设置为BINDER_WORK_DEAD_BINDER。

- 当Client进程向binder驱动程序注册一个死亡接收通知时，如果它所引用的Service组件已经死亡，那么binder驱动程序就会马上发送一个死亡通知给该Client进程。在这种情况下，binder驱动程序也会将死亡通知的类型设置为BINDER_WORK_DEAD_BINDER。


client 也可以注销一个死亡监听，在注销的时候，binder 驱动也会发送一个类型为 binder_ref_death 的工作项到 client 进程的 todo 队列中。

- 如果Client进程在注销一个死亡接收通知时，相应的Service组件还没有死亡，那么binder驱动程序就会找到之前所注册的一个binder_ref_death结构体，并且将它的类型work修改为BINDER_WORK_CLEAR_DEATH_NOTIFICATION，然后再将该binder_ref_death结构体封装成一个工作项添加到该Client进程的todo队列中去等待处理。

- 如果Client进程在注销一个死亡接收通知时，相应的Service组件已经死亡，那么binder驱动程序就会找到之前所注册的一个binder_ref_death结构体，并且将它的类型work修改为BINDER_WORK_DEAD_BINDER_AND_CLEAR，然后再将该binder_ref_death结构体封装成一个工作项添加到该Client进程的todo队列中去等待处理。

### binder_ref

binder_ref 代表一个进程对另一个进程 binder 实体对象 (binder_node) 的引用。在 binder 体系中，每个进程只能通过 handle（整数句柄）来引用别的进程的 binder 服务对象，而不能直接访问 binder_node。handle 和 binder_node 的映射关系，就是由 `binder_ref` 结构体来维护的。

```c
struct binder_ref {
	/* Lookups needed: */
	/*   node + proc => ref (transaction) */
	/*   desc + proc => ref (transaction, inc/dec ref) */
	/*   node => refs + procs (proc exit) */
	int debug_id;
	struct rb_node rb_node_desc;
	struct rb_node rb_node_node;
	struct hlist_node node_entry; // binder_node 会有一个 hlist_head refs 成员保存所有引用了他的 binder_ref, 这个node_entry 就是对应的节点。
	struct binder_proc *proc;  // 拥有这个引用的进程，一般来说是 client 所在的进程。
	struct binder_node *node; // 引用的实体对象 binder_node
	uint32_t desc;  // 句柄值或者称为描述符，它是用来描述一个binder引用对象的。在Client进程的用户空间中，一个binder引用对象是使用一个句柄值来描述的，因此，当Client进程的用户空间通过binder驱动程序来访问一个Service组件时，它只需要指定一个句柄值，binder驱动程序就可以通过该句柄值找到对应的binder引用对象，然后再根据该binder引用对象的成员变量node找到对应的binder实体对象，最后就可以通过该binder实体对象找到要访问的Service组件。
	int strong;
	int weak;
	struct binder_ref_death *death;
};
```

desc 在一个进程范围内是唯一的，也就是说在不同的进程下，同一个 desc 可能代表不同的的 binder_node。

rb_node_desc 和 rb_node_node 这两个都是红黑树节点，每一个与binder 驱动交互的进程，都会构建了两个红黑树(维护在 binder_proc 结构中)，第一个以 desc 为 key ，第二个以 binder_node 为 key。这样子 binder 驱动可以高效的以 desc 或者 node 来查找到对应的 binder_ref。

- 以 desc 查找，主要用在 client 发起事务请求。
- 以 node 查找，主要用在服务端进程发送死亡通知，引用管理等。

我这里有个疑问：refs_by_node 这个有必要吗，每一个 binder_node 不是会持有一个 refs 的hash 列表，里面保存着所有的 binder_ref 吗？

主要是使用场景，refs 这个 hash 列表用于一个一个 binder_node 节点快速查看有哪些实体引用了自己。而 refs_by_node 服务的是 binder_proc, 只需要知道 node 节点，就可以找到对应的引用信息，即查找自己引用了哪些其余的实体。

最后，death 存放的是死亡监听结构体，用于 server 死亡后发送死亡监听时提供输入信息。

### binder_buffer

binder_buffer 用来描述一个内核缓冲区，这个缓冲区用来进行进程间通信数据传输。每一个使用 binder rpc 的进程在内核中都有一个缓冲区队列，每一个 binder 通信的缓冲区就取自于这个队列中的一个节点，节点就是 entry。

同时为了更高效的管理，每个进程维护了两棵红黑树，一棵树维护的是在使用中的 buffer，一颗维护着空闲的buffer，free 的值代表当前是不是空闲。

成员变量transaction和target_node用来描述一个内核缓冲区正在交给哪一个事务以及哪一个binder实体对象使用。

sync_transaction 表明当前事务是不是异步事务，binder驱动程序限制了分配给异步事务的内核缓冲区的大小，这样做的目的是为了保证同步事务可以优先得到内核缓冲区，以便可以快速地对该同步事务进行处理。

```c
struct binder_buffer {
	struct list_head entry; /* free and allocated entries by addesss */
	struct rb_node rb_node; /* free entry by size or allocated entry */
				/* by address */
	unsigned free : 1;
	unsigned allow_user_free : 1; // server 在处理完成事务后，是否可以决定释放缓冲区。
	unsigned async_transaction : 1; // 如果当前事务是一个异步事务，这个位置会设置成 1
	unsigned debug_id : 29;

	struct binder_transaction *transaction;

	struct binder_node *target_node;
	size_t data_size;
	size_t offsets_size;
	uint8_t data[0];
};
```

成员变量data指向一块大小可变的数据缓冲区，它是真正用来保存通信数据的。数据缓冲区保存的数据划分为两种类型，其中一种是普通数据，另一种是binder对象。

binder驱动程序不关心数据缓冲区中的普通数据，但是必须要知道里面的binder对象，因为它需要根据它们来维护内核中的binder实体对象和binder引用对象的生命周期。

例如，如果数据缓冲区中包含了一个binder引用，并且该数据缓冲区是传递给另外一个进程的，那么binder驱动程序就需要为另外一个进程创建一个binder引用对象，并且增加相应的binder实体对象的引用计数，因为它也被另外的这个进程引用了。

由于数据缓冲区中的普通数据和binder对象是混合在一起保存的，它们之间并没有固定的顺序，因此，binder驱动程序就需要额外的数据来找到里面的binder对象。在数据缓冲区的后面，有一个偏移数组，它记录了数据缓冲区中每一个binder对象在数据缓冲区中的位置。偏移数组的大小保存在成员变量offsets_size中，而数据缓冲区的大小保存在成员变量data_size中。


### binder_proc

结构体binder_proc用来描述一个正在使用binder进程间通信机制的进程。当一个进程调用函数open来打开设备文件/dev/binder时，binder驱动程序就会为它创建一个binder_proc结构体，并且将它保存在一个全局的hash列表中，而成员变量proc_node就正好是该hash列表中的一个节点。

此外，成员变量pid、tsk和files分别指向了进程的进程组ID、任务控制块(😯，PCB!)和打开文件结构体数组。

在打开了 binder 设备文件的进程中，一般后续还需要 mmap，我们对于普通文本文件进行 mmap 操作和对 binder 是不一样的，对于一个普通的文本文件，mmap 由内核进行处理。而对于 binder，mmap 会触发 binder 驱动注册的 .mmap 函数，这个函数进行实际的 mmap 动作。放在 binder 这里，就是 binder 驱动程序为它分配一块内核缓冲区，以便可以用来在进程间传输数据。

binder 驱动程序为进程分配的内核缓冲区的大小保存在成员变量 buffer_size 中。这些内核缓冲区有两个地址，其中一个是内核空间地址，另外一个是用户空间地址。内核空间地址是在 binder 驱动程序内部使用的，保存在成员变量buffer 中，而用户空间地址是在应用程序进程内部使用的，保存在成员变量 vma 中。这两个地址相差一个固定的值，保存在成员变量 user_buffer_offset 中。这样，给定一个用户空间地址或者一个内核空间地址，binder 驱动程序就可以计算出另外一个地址的大小。

当进程接收到一个进程间通信请求时，binder 驱动程序就将该请求封装成一个工作项，并且加入到进程的待处理工作项队列中，这个队列使用成员变量 todo 来描述。

binder线程池中的空闲binder线程会睡眠在由成员变量wait所描述的一个等待队列中，当它们的宿主进程的待处理工作项队列增加了新的工作项之后，binder驱动程序就会唤醒这些线程，以便它们可以去处理新的工作项。

一个进程内部包含了一系列的binder实体对象和binder引用对象，进程使用三个红黑树来组织它们，其中，成员变量nodes所描述的红黑树是用来组织binder实体对象的，它以binder实体对象的成员变量ptr作为关键字；而成员变量refs_by_desc和refs_by_node所描述的红黑树是用来组织binder引用对象的，前者以binder引用对象的成员变量desc作为关键字，而后者以binder引用对象的成员变量node作为关键字。

而成员变量refs_by_desc和refs_by_node所描述的红黑树是用来组织binder引用对象的，前者以binder引用对象的成员变量desc作为关键字，而后者以binder引用对象的成员变量node作为关键字。

```c
struct binder_proc {
	struct hlist_node proc_node;
	struct rb_root threads;						// 每一个 binder 进程进程间通信都会有一个单独的线程来处理，这个节点就是线程池的红黑树根节点，key 是 tid。
	struct rb_root nodes;						// 保存着进程持有的所有 binder_node 对象, 以 node 的 ptr 成员为 key。
	struct rb_root refs_by_desc;
	struct rb_root refs_by_node;
	int pid;  									// 进程组ID
	struct vm_area_struct *vma;					// mmap 后，binder 缓冲区映射到用户空间的地址
	struct task_struct *tsk;					// 任务控制块
	struct files_struct *files;					// 文件结构体数组
	struct hlist_node deferred_work_node;		// 一些可以延迟执行的工作项
	int deferred_work;							// 一个 flag，由所有的延迟类型任务组合起来，用来表示当前进程有哪些类型的延迟任务
	void *buffer;								// mmap 后，binder 缓冲区内核空间地址
	ptrdiff_t user_buffer_offset;				// binder 缓冲区 内核空间地址和用户空间地址的偏移量

	struct list_head buffers;					// 对 buffer 缓冲区进行划分小块，每一个就是一个 binder_buffer 结构体。整体是个链表，这个 buffers 就是链表头。
	struct rb_root free_buffers;				// 红黑树节点，保存的是所有没有使用到的 binder_buffer. 目的是为了更高效的查找。key 是 buffer 的大小。
	struct rb_root allocated_buffers;			// 红黑树节点，保存的是所有正在使用到的 binder_buffer. 目的是为了更高效的查找。key 是 buffer 的地址。
	size_t free_async_space;

	struct page **pages;						// 物理页面地址存储
	size_t buffer_size;
	uint32_t buffer_free;
	struct list_head todo;						// 该进程待处理工作序列
	wait_queue_head_t wait;						// 空闲的可以处理任务的等待队列
	struct binder_stats stats;
	struct list_head delivered_death;
	int max_threads;
	int requested_threads;
	int requested_threads_started;
	int ready_threads;
	long default_priority;
};
```

成员变量deferred_work_node是一个hash列表，用来保存进程可以延迟执行的工作项。这些延迟工作项有三种类型，如下所示:

首先明确的是，这三种延迟任务都是由 binder 驱动内核去做的，而不是和 todo 一样分发给进程去做。

- BINDER_DEFERRED_PUT_FILES: 当进程通过 binder 传递了文件描述符，内核需要在消息传递完成后，适时地关闭或释放这些文件描述符。有时不能立刻释放（比如还在被使用），所以会把“释放文件描述符”这个操作延迟到合适时机（比如消息处理完成后）。
- BINDER_DEFERRED_FLUSH: “Flush” 意为“刷新”，在 binder 驱动中，通常指的是把积累的消息、命令等数据从内核缓冲区刷新到目标进程的消息队列中。有时出于效率或同步的考虑，不会每次消息到达都立即刷新，而是延迟到合适时机批量处理。
- BINDER_DEFERRED_RELEASE: 当进程退出、断开 binder 连接或某些资源不再需要时，binder 驱动需要清理和释放相关资源。由于资源释放可能涉及复杂的依赖关系（比如还有其他进程引用），或者为了避免在关键路径上阻塞，binder 驱动会把这些释放操作延迟到后续统一处理。

```c
enum {
	BINDER_DEFERRED_PUT_FILES    = 0x01,
	BINDER_DEFERRED_FLUSH        = 0x02,
	BINDER_DEFERRED_RELEASE      = 0x04,
};
```

### binder_thread

binder_thread 用来描述 binder 线程池中的一个线程，proc 指向其宿主进程 binder_proc, rb_node 是 proc 中 threads 红黑树的节点。

```c
struct binder_thread {
	struct binder_proc *proc;
	struct rb_node rb_node;
	int pid; // 线程 id，这里因为 linux 下线程和进程的形式差不多，所以这里的名字也就叫 pid。
	int looper;
	struct binder_transaction *transaction_stack;
	struct list_head todo;
	uint32_t return_error; /* Write failed, return error code in read buf */
	uint32_t return_error2; /* Write failed, return error code in read */
		/* buffer. Used when sending a reply to a dead process that */
		/* we are also waiting on */
	wait_queue_head_t wait;
	struct binder_stats stats;
};
```

binder_thread 一个线程一般会不断的循环等待处理 binder 消息，所以为了描述这个循环等待的状态，引入了一个成员 looper，有下面几种类型，现在这些状态的含义先按下不表，等后面学习 binder 驱动流程的时候自然就会提到。

```c
enum {
	BINDER_LOOPER_STATE_REGISTERED  = 0x01,
	BINDER_LOOPER_STATE_ENTERED     = 0x02,
	BINDER_LOOPER_STATE_EXITED      = 0x04,
	BINDER_LOOPER_STATE_INVALID     = 0x08,
	BINDER_LOOPER_STATE_WAITING     = 0x10,
	BINDER_LOOPER_STATE_NEED_RETURN = 0x20
};
```

当一个来自 Client 进程的请求指定要由某一个 binder 线程来处理时，这个请求就会加入到相应的 binder_thread 结构体的成员变量 todo 所表示的队列中，并且会唤醒这个线程来处理，因为这时候这个线程可能处于睡眠状态。

当 binder 驱动程序决定将一个事务交给一个 binder 线程处理时，它就会将该事务封装成一个 binder_transaction 结构体，并且将它添加到由线程结构体 binder_thread 的成员变量 transaction_stack 所描述的一个事务堆栈中

当一个 binder 线程在处理一个事务 T1 并需要依赖于其他的 binder 线程来处理另外一个事务 T2 时，它就会睡眠在由成员变量 wait 所描述的一个等待队列中，直到事务 T2 处理完成为止。

一个 binder 线程在处理一个事务时，如果出现了异常情况，那么 Binde r驱动程序就会将相应的错误码保存在其成员变量 return_error 和 reutrn_error2 中，这时候线程就会将这些错误返回给用户空间应用程序处理。

