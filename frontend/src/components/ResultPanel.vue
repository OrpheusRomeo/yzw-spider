<template>
  <el-card shadow="never" class="panel">
    <template #header>
      <div class="card-header">
        <span class="card-title">结果文件</span>
        <el-button link type="primary" size="small" @click="load">刷新</el-button>
      </div>
    </template>

    <div v-if="!files.length" class="empty">
      还没有结果文件。抓完之后 CSV / JSON / Excel 会出现在这里。
    </div>

    <el-table v-else :data="files" size="small" max-height="380">
      <el-table-column prop="name" label="文件" min-width="220" show-overflow-tooltip />
      <el-table-column prop="modified" label="时间" width="150" />
      <el-table-column label="大小" width="100" align="right">
        <template #default="scope">
          {{ formatSize(scope.row.size) }}
        </template>
      </el-table-column>
      <el-table-column label="" width="80" align="right">
        <template #default="scope">
          <a :href="downloadUrl(scope.row.path)">
            <el-button link type="primary" size="small">下载</el-button>
          </a>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const files = ref([])

function formatSize(size) {
  const value = Number(size) || 0
  if (value < 1024) {
    return value + ' B'
  }
  if (value < 1024 * 1024) {
    return (value / 1024).toFixed(1) + ' KB'
  }
  return (value / 1024 / 1024).toFixed(1) + ' MB'
}

function downloadUrl(path) {
  return '/api/results/download?path=' + encodeURIComponent(path)
}

async function load() {
  try {
    files.value = await api.results()
  } catch (error) {
    files.value = []
  }
}

onMounted(load)
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-weight: 600;
}

.empty {
  color: #909399;
  padding: 24px 0;
  text-align: center;
}
</style>
