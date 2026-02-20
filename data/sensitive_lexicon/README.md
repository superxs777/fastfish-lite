# 敏感词库目录

敏感词检测需在此目录下放置词库文件。

## 获取词库

1. 克隆 [Sensitive-lexicon](https://github.com/konsheng/Sensitive-lexicon) 或类似开源词库
2. 将 `Vocabulary` 目录下的 txt 文件复制到本目录的 `Vocabulary` 子目录中

## 目录结构

```
data/sensitive_lexicon/
└── Vocabulary/
    ├── 广告类型.txt
    ├── 色情类型.txt
    ├── 色情词库.txt
    ├── 政治类型.txt
    ├── 反动词库.txt
    ├── 补充词库.txt
    └── 其他词库.txt
```

若目录不存在或为空，将跳过敏感词检测。
