import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  RefreshControl, ActivityIndicator, Platform, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { Briefcase, TrendingUp, TrendingDown, X, DollarSign } from 'lucide-react-native';

const API = process.env.EXPO_PUBLIC_BACKEND_URL;

const C = {
  bg: '#030206',
  surface: '#0D0814',
  surfaceHi: '#1A1025',
  border: '#321B4D',
  primary: '#9D4CDD',
  success: '#39FF14',
  successBg: 'rgba(57, 255, 20, 0.1)',
  danger: '#FF2A2A',
  dangerBg: 'rgba(255, 42, 42, 0.1)',
  warning: '#FFD700',
  text: '#F4F0FF',
  textSec: '#A390C2',
  muted: '#5C4A7A',
};

export default function PortfolioScreen() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<'open' | 'closed'>('open');

  const fetchPortfolio = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/portfolio`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchPortfolio(); }, [fetchPortfolio]);

  useEffect(() => {
    const interval = setInterval(fetchPortfolio, 6000);
    return () => clearInterval(interval);
  }, [fetchPortfolio]);

  const closePosition = async (id: string) => {
    try {
      await fetch(`${API}/api/portfolio/close/${id}`, { method: 'POST' });
      await fetchPortfolio();
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="light" />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={C.primary} />
        </View>
      </SafeAreaView>
    );
  }

  const stats = data?.stats || {};
  const openPositions = data?.open_positions || [];
  const closedPositions = data?.closed_positions || [];
  const positions = tab === 'open' ? openPositions : closedPositions;

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />

      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Briefcase color={C.primary} size={22} />
          <Text style={styles.headerTitle}>PORTFOLIO</Text>
        </View>
      </View>

      {/* P&L Header */}
      <View style={styles.pnlHeader}>
        <View style={styles.pnlRow}>
          <View style={styles.pnlBlock}>
            <Text style={styles.pnlLabel}>REALIZED P&L</Text>
            <Text style={[styles.pnlValue, {
              color: stats.realized_pnl_sol >= 0 ? C.success : C.danger,
            }]}>
              {stats.realized_pnl_sol >= 0 ? '+' : ''}{stats.realized_pnl_sol?.toFixed(4) || '0.0000'}
              <Text style={styles.pnlUnit}> SOL</Text>
            </Text>
          </View>
          <View style={styles.pnlBlock}>
            <Text style={styles.pnlLabel}>UNREALIZED P&L</Text>
            <Text style={[styles.pnlValue, {
              color: stats.unrealized_pnl_sol >= 0 ? C.success : C.danger,
            }]}>
              {stats.unrealized_pnl_sol >= 0 ? '+' : ''}{stats.unrealized_pnl_sol?.toFixed(4) || '0.0000'}
              <Text style={styles.pnlUnit}> SOL</Text>
            </Text>
          </View>
        </View>
        <View style={styles.pnlRow}>
          <View style={styles.miniStat}>
            <Text style={styles.miniStatLabel}>SNIPED</Text>
            <Text style={styles.miniStatValue}>{stats.total_sniped || 0}</Text>
          </View>
          <View style={styles.miniStat}>
            <Text style={styles.miniStatLabel}>WIN RATE</Text>
            <Text style={[styles.miniStatValue, { color: C.success }]}>{stats.win_rate || 0}%</Text>
          </View>
          <View style={styles.miniStat}>
            <Text style={styles.miniStatLabel}>PROFITABLE</Text>
            <Text style={styles.miniStatValue}>{stats.profitable || 0}</Text>
          </View>
        </View>
      </View>

      {/* Tab Selector */}
      <View style={styles.tabRow}>
        <TouchableOpacity
          testID="portfolio-open-tab"
          style={[styles.tabBtn, tab === 'open' && styles.tabActive]}
          onPress={() => setTab('open')}
        >
          <Text style={[styles.tabText, tab === 'open' && styles.tabTextActive]}>
            OPEN ({openPositions.length})
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          testID="portfolio-closed-tab"
          style={[styles.tabBtn, tab === 'closed' && styles.tabActive]}
          onPress={() => setTab('closed')}
        >
          <Text style={[styles.tabText, tab === 'closed' && styles.tabTextActive]}>
            CLOSED ({closedPositions.length})
          </Text>
        </TouchableOpacity>
      </View>

      {/* Positions List */}
      {positions.length === 0 ? (
        <View style={styles.emptyContainer}>
          <DollarSign color={C.muted} size={48} strokeWidth={1} />
          <Text style={styles.emptyText}>NO {tab.toUpperCase()} POSITIONS</Text>
        </View>
      ) : (
        <FlatList
          data={positions}
          keyExtractor={(item) => item.id}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchPortfolio(); }} tintColor={C.primary} />
          }
          renderItem={({ item }) => (
            <View style={styles.posCard}>
              <View style={styles.posHeader}>
                <View style={styles.posLeft}>
                  {item.pnl_pct >= 0 ? (
                    <TrendingUp color={C.success} size={18} />
                  ) : (
                    <TrendingDown color={C.danger} size={18} />
                  )}
                  <Text style={styles.posName}>{item.token_name}</Text>
                  <Text style={styles.posPlatform}>{item.platform}</Text>
                </View>
                {tab === 'open' && (
                  <TouchableOpacity
                    testID={`close-position-${item.id}`}
                    style={styles.closeBtn}
                    onPress={() => closePosition(item.id)}
                  >
                    <X color={C.danger} size={16} />
                  </TouchableOpacity>
                )}
              </View>

              <View style={styles.posBody}>
                <View style={styles.posMetric}>
                  <Text style={styles.posMetricLabel}>ENTRY</Text>
                  <Text style={styles.posMetricValue}>{item.amount_sol} SOL</Text>
                </View>
                <View style={styles.posMetric}>
                  <Text style={styles.posMetricLabel}>CURRENT</Text>
                  <Text style={styles.posMetricValue}>{item.current_value_sol?.toFixed(4)} SOL</Text>
                </View>
                <View style={styles.posMetric}>
                  <Text style={styles.posMetricLabel}>P&L</Text>
                  <Text style={[styles.posMetricValue, {
                    color: item.pnl_pct >= 0 ? C.success : C.danger,
                  }]}>
                    {item.pnl_pct >= 0 ? '+' : ''}{item.pnl_pct?.toFixed(1)}%
                  </Text>
                </View>
              </View>

              <View style={styles.posFooter}>
                <Text style={styles.posFooterText}>Safety: {item.safety_score}/100</Text>
                <Text style={styles.posFooterText}>TP1: {item.tp1_hit ? 'YES' : 'no'}</Text>
                {item.close_reason && (
                  <Text style={[styles.posFooterText, { color: C.warning }]}>
                    {item.close_reason}
                  </Text>
                )}
              </View>
            </View>
          )}
          contentContainerStyle={{ paddingBottom: 32 }}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#030206' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 20, paddingTop: 12, paddingBottom: 12,
    borderBottomWidth: 1, borderBottomColor: '#321B4D',
  },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  headerTitle: { color: '#F4F0FF', fontSize: 22, fontWeight: '800', letterSpacing: 2 },

  pnlHeader: {
    paddingHorizontal: 16, paddingVertical: 16,
    backgroundColor: '#0D0814', borderBottomWidth: 1, borderBottomColor: '#321B4D',
  },
  pnlRow: { flexDirection: 'row', gap: 12, marginBottom: 12 },
  pnlBlock: { flex: 1 },
  pnlLabel: { color: '#5C4A7A', fontSize: 9, fontWeight: '700', letterSpacing: 3, marginBottom: 4 },
  pnlValue: { fontSize: 22, fontWeight: '900' },
  pnlUnit: { fontSize: 12, color: '#A390C2' },

  miniStat: { flex: 1, alignItems: 'center' },
  miniStatLabel: { color: '#5C4A7A', fontSize: 8, fontWeight: '700', letterSpacing: 2, marginBottom: 2 },
  miniStatValue: { color: '#F4F0FF', fontSize: 18, fontWeight: '800' },

  tabRow: {
    flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 12, gap: 12,
  },
  tabBtn: {
    flex: 1, paddingVertical: 10, alignItems: 'center',
    borderWidth: 1, borderColor: '#321B4D', borderRadius: 4,
    backgroundColor: '#0D0814',
  },
  tabActive: { borderColor: '#9D4CDD', backgroundColor: 'rgba(157, 76, 221, 0.15)' },
  tabText: { color: '#5C4A7A', fontSize: 12, fontWeight: '700', letterSpacing: 2 },
  tabTextActive: { color: '#9D4CDD' },

  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  emptyText: { color: '#5C4A7A', fontSize: 14, fontWeight: '700', letterSpacing: 3 },

  posCard: {
    marginHorizontal: 16, marginBottom: 10,
    backgroundColor: '#0D0814', borderWidth: 1, borderColor: '#321B4D', borderRadius: 6,
    padding: 14,
  },
  posHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12,
  },
  posLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  posName: { color: '#F4F0FF', fontSize: 16, fontWeight: '700' },
  posPlatform: { color: '#5C4A7A', fontSize: 10, fontWeight: '600' },
  closeBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: 'rgba(255,42,42,0.1)', borderWidth: 1, borderColor: '#FF2A2A',
    justifyContent: 'center', alignItems: 'center',
  },

  posBody: { flexDirection: 'row', gap: 12, marginBottom: 10 },
  posMetric: { flex: 1 },
  posMetricLabel: { color: '#5C4A7A', fontSize: 9, fontWeight: '700', letterSpacing: 2, marginBottom: 2 },
  posMetricValue: { color: '#F4F0FF', fontSize: 14, fontWeight: '700' },

  posFooter: { flexDirection: 'row', gap: 16 },
  posFooterText: { color: '#5C4A7A', fontSize: 10 },
});
