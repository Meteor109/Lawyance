# 普通法系库构建清单（BUILD）

## 1. 语料

| 国家 | 目录 | 内容 |
|---|---|---|
| 缅甸 `MM` | `data/MM/documents.jsonl` | 685 份 MOI 法律文件，含条款候选；`legal_system=common` |
| 新加坡 `SG` | `data/SG/corpus/part-*.jsonl.gz` | 28,451 份官方公报、57,826 条检索记录 |

新加坡完整语料以 12 个 gzip JSONL 分片提交，压缩后共 108,081,635 字节，每个文件低于 50 MiB。普通 Git 拉取即可取得全部语料，无需 Git LFS 或另行下载。`corpus/manifest.json` 保存分片数量、大小及 SHA-256；加载器检查分片列表、哈希和总数量，漏传或损坏时报错。

压缩前 JSONL SHA-256：`7b5e2c19ed5a49623cb593d858a486110196050c3f5fc7fac983cfab7c6650ef`。

默认优先读取完整分片目录；没有分片和交付清单时才回退到 `official_seed.json` 的 10 条接口回归样本。启动前可用 `SINGAPORE_LAW_DATA_PATH` 指定 JSON 数组、JSONL、gzip JSONL 或分片目录，用 `SINGAPORE_LAW_CACHE_DIR` 指定缓存目录。

完整语料不是已核验的现行法全集。出版范围为 1998 年 9 月至 2026 年 9 月 15 日：Acts Supplement 1,104、Bills Supplement 1,088、Subsidiary Legislation Supplement 23,100、Revised Acts 987、Revised Subsidiary Legislation 1,770、Corrigenda 402。记录主要按页面分组，并保留 10 条已核对 section 样本。Bills 保持 `bill`、更正材料保留复核标记；公报发布不能证明现行整合状态或生效日期。SSO 现行状态、早于 1998 年 9 月的公报和判例尚未接入。一个页树损坏的官方 PDF 保留来源元数据，正文缺失。

## 2. 构建

```bash
.venv/bin/python -m RAG.common_law.scripts.assembly_smoke_cases
.venv/bin/python -c "from RAG.common_law import ensure_common_law_database_ready as e; print(e(force_rebuild=True))"
```

部署时在仓库根目录拉取最新代码，使用项目 Python 环境运行上述命令。验收数量：新加坡 `record_count=57826`；缅甸 `document_count=685`、`entry_count=13122`。再次初始化不加 `force_rebuild` 时，两国分别返回 `unchanged` 与 `reuse`。

后端启动已有普通法系初始化接线；部署后还需核对服务器启动日志及实际应用检索。本地检查不代替线上验收。首次构建新加坡 SQLite 约 2.55 GB、缅甸约 103 MB；更新新加坡时会先建立临时索引，建议预留至少 6 GB 可用磁盘及足够内存。加载器流式解压、分批插入，无需预先解压语料。

缅甸的 13,122 条记录包括 12,792 条机器切分候选与 330 条整份文件回退；4 份不可读文件排除，58 条下载未成功附件关系已记录。OCR、条款边界、未知效力保留复核要求。两国 `semantic_search` 都是 fuzzy 检索兼容接口，没有向量索引。

缅甸语料若要从 OCR 流水线重做：

```bash
.venv/bin/python -m RAG.common_law.build_corpus \
  --metadata "<MOI metadata>/legal_metadata.json" \
  --relations "<MOI downloads>/document_file_relations.json" \
  --merged-root "<formal OCR output>" \
  --provision-root "<formal OCR output>"
```

默认写到 `data/MM/documents.jsonl`。

## 3. 缓存

- `cache/myanmar_law.db`
- `cache/singapore_law.db`
- `cache/myanmar_manifest.json`
- `cache/singapore_manifest.json`

语料指纹变了会重建。两国清单独立，旧共享 `cache/manifest.json` 不再读取；升级首次会建立新清单，以后复用。`cache/` 不提交。

## 4. 回归检查

```bash
python -m pytest tests/test_singapore_law.py tests/test_myanmar_law.py -q
```

单元测试用隔离小语料验证接口、分片校验、数据变更重建及缓存清单隔离；完整数量和检索由 assembly smoke 验收。
