<template>
  <div class="backlog">
    <div class="page-header">
      <h2>{{ t('backlog.title') }}</h2>
      <p>{{ t('backlog.subtitle') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('backlog.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="stats-grid">
        <div class="stat-card danger">
          <div class="stat-label">{{ t('backlog.stats.highPriority') }}</div>
          <div class="stat-value">{{ priorityCounts.high }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('backlog.stats.mediumPriority') }}</div>
          <div class="stat-value">{{ priorityCounts.medium }}</div>
        </div>
        <div class="stat-card info">
          <div class="stat-label">{{ t('backlog.stats.lowPriority') }}</div>
          <div class="stat-value">{{ priorityCounts.low }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('backlog.stats.total') }}</div>
          <div class="stat-value">{{ backlogItems.length }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('backlog.tableTitle') }}</h3>
        </div>
        <div v-if="backlogItems.length === 0" class="no-backlog">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="success-icon">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
          <p class="no-backlog-text">{{ t('backlog.noBacklog') }}</p>
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('dashboard.inventoryShortages.orderId') }}</th>
                <th>{{ t('dashboard.inventoryShortages.sku') }}</th>
                <th>{{ t('dashboard.inventoryShortages.itemName') }}</th>
                <th>{{ t('dashboard.inventoryShortages.quantityNeeded') }}</th>
                <th>{{ t('dashboard.inventoryShortages.quantityAvailable') }}</th>
                <th>{{ t('dashboard.inventoryShortages.shortage') }}</th>
                <th>{{ t('dashboard.inventoryShortages.daysDelayed') }}</th>
                <th>{{ t('dashboard.inventoryShortages.priority') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in backlogItems" :key="item.id">
                <td><strong>{{ item.order_id }}</strong></td>
                <td><strong>{{ item.item_sku }}</strong></td>
                <td>{{ item.item_name }}</td>
                <td>{{ item.quantity_needed }}</td>
                <td>{{ item.quantity_available }}</td>
                <td>
                  <span class="badge danger">
                    {{ item.quantity_needed - item.quantity_available }} {{ t('dashboard.inventoryShortages.unitsShort') }}
                  </span>
                </td>
                <td>
                  <span :class="getDaysDelayedClass(item.days_delayed)">
                    {{ item.days_delayed }} {{ t('dashboard.inventoryShortages.days') }}
                  </span>
                </td>
                <td>
                  <span :class="['badge', item.priority]">
                    {{ translatePriority(item.priority) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from '../composables/useI18n'
import { useFilters } from '../composables/useFilters'
import { api } from '../api'

export default {
  name: 'Backlog',
  setup() {
    const { t } = useI18n()
    const { selectedLocation, selectedCategory, getCurrentFilters } = useFilters()

    const loading = ref(true)
    const error = ref(null)
    const backlogItems = ref([])

    // Count by priority in a single pass — avoids three separate filter passes per render
    const priorityCounts = computed(() => {
      const c = { high: 0, medium: 0, low: 0 }
      for (const item of backlogItems.value) {
        if (c[item.priority] !== undefined) c[item.priority]++
      }
      return c
    })

    const loadData = async () => {
      loading.value = true
      error.value = null
      try {
        const filters = getCurrentFilters()
        backlogItems.value = await api.getBacklog({
          warehouse: filters.warehouse,
          category: filters.category
        })
      } catch (err) {
        error.value = 'Failed to load backlog: ' + err.message
        console.error('Backlog load error:', err)
      } finally {
        loading.value = false
      }
    }

    // Backlog is not temporal and has no order status — only warehouse/category apply
    watch([selectedLocation, selectedCategory], () => {
      loadData()
    })

    onMounted(loadData)

    const translatePriority = (priority) => {
      const map = {
        high: t('priority.high'),
        medium: t('priority.medium'),
        low: t('priority.low'),
        High: t('priority.high'),
        Medium: t('priority.medium'),
        Low: t('priority.low')
      }
      return map[priority] || priority
    }

    // Returns a CSS class instead of an inline style so colors live in <style scoped>
    const getDaysDelayedClass = (days) => {
      return days > 7 ? 'days-delayed-high' : 'days-delayed-medium'
    }

    return {
      t,
      loading,
      error,
      backlogItems,
      priorityCounts,
      translatePriority,
      getDaysDelayedClass
    }
  }
}
</script>

<style scoped>
.backlog {
  padding: 2rem;
}

.page-header {
  margin-bottom: 2rem;
}

.page-header h2 {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 0.25rem;
}

.page-header p {
  color: #64748b;
  margin: 0;
}

.loading {
  text-align: center;
  padding: 3rem;
  color: #64748b;
}

.error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
  padding: 1rem;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 1.25rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.stat-card.danger { border-left: 4px solid #ef4444; }
.stat-card.warning { border-left: 4px solid #f59e0b; }
.stat-card.info    { border-left: 4px solid #3b82f6; }

.stat-label {
  font-size: 0.875rem;
  color: #64748b;
  margin-bottom: 0.5rem;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: #0f172a;
}

.card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  margin-bottom: 1.5rem;
}

.card-header {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.card-title {
  font-size: 1rem;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
}

.no-backlog {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  gap: 0.75rem;
}

.success-icon {
  width: 2.5rem;
  height: 2.5rem;
  color: #10b981;
}

.no-backlog-text {
  font-size: 1.125rem;
  font-weight: 600;
  color: #10b981;
  margin: 0;
}

.table-container {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead th {
  padding: 0.75rem 1rem;
  text-align: left;
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

tbody td {
  padding: 0.875rem 1rem;
  font-size: 0.875rem;
  color: #334155;
  border-bottom: 1px solid #f1f5f9;
}

tbody tr:last-child td {
  border-bottom: none;
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge.danger  { background: #fef2f2; color: #dc2626; }
.badge.warning { background: #fffbeb; color: #d97706; }
.badge.high    { background: #fef2f2; color: #dc2626; }
.badge.medium  { background: #fffbeb; color: #d97706; }
.badge.low     { background: #f0fdf4; color: #16a34a; }

/* Days-delayed colour classes — replaces the former inline :style binding */
.days-delayed-high   { color: #ef4444; font-weight: 600; }
.days-delayed-medium { color: #f59e0b; font-weight: 600; }
</style>
