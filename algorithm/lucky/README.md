# 运气题

什么是运气题呢？就是没有明显的特征，我们无法套路到已知的方案，例如 dp、贪心等等。往往需要我们在深刻理解题目后的灵光一现。但是我想说的是，这种题目如果可以暴力解决，而且题目没有强制要求时间复杂度或者空间复杂度，那就暴力解决吧，头发重要。

## [两数之和](https://leetcode.cn/problems/two-sum/description/)

1. Don't code! Think!

给定我们一个整数 n 以及一个整数数组 x，题目要求我们从数组中找出两个数，这两个数的和恰好等于 n，而且这两个数不应该是同一个。

而且每种输入只会对应一个答案，这意味着我们找到一个后就可以返回了，而且过程中不需要记录，也不需要去重，看起来简单很多。

我们都会想到的方法就是使用暴力解法，构建两个循环，for(i) 和 for(j) 其中 i 不等与 j，判断 x[i] + x[j] 是不是和 n 相等，相等就返回。时间复杂度是 O(n^2)。

按照这个思路先去跑一次测试，时间复杂度只击败了 5% 的人，不过也可以 ac，

```cpp
vector<int> twoSum(vector<int>& nums, int target) {
        int x, y;
        for(int i = 0; i < nums.size(); ++i){
            for(int j = 0; j < nums.size(); ++j){
                if(j == i){
                    continue;
                }
                if(nums[i]+nums[j] == target){
                    x = i;
                    y = j;
                    return {x, y};
                }
            }
        }
        return {x, y};
}
```

