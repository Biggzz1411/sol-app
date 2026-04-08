import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  RefreshControl, ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { Radar, ShieldCheck, ShieldAlert, Zap, Clock } from 'lucide-react-native';

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
  pumpfun: '#39FF14',
  raydium: '#5E17EB',
  pumpswap: '#FF8C00',
};

const platformColor = (p: string) => {
  if (p === 'pump.fun') return C.pumpfun;
  if (p === 'raydium') return C.raydium;
  if (p === 'pumpswap') return C.pumpswap;
  return C.muted;
};

export default function ScannerScreen() {
  const [feed, setFeed] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [selectedToken, setSelectedToken] = useState<any>(null);
  const [audit, setAudit] = useState<any>(null);

  const fetchFeed = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/scanner/feed?limit=50`);
      const data = await res.json();
      setFeed(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchFeed(); }, [fetchFeed]);

  useEffect(() => {
    const interval = setInterval(fetchFeed, 4000);
    return () => clearInterval(interval);
  }, [fetchFeed]);

  const simulateDetection = async () => {
    setSimulating(true);
    try {
      await fetch(`${API}/api/scanner/simulate`, { method: 'POST' });
      await fetchFeed();
    } catch (e) {
      console.error(e);
    } finally {
      setSimulating(false);
    }
  };

  const viewAudit = async (item: any) => {
    setSelectedToken(item);
    try {
      const res = await fetch(`${API}/api/safety/${item.token_mint}`);
      const data = await res.json();
      setAudit(data);
    } catch (e) {
      console.error(e);
    }
  };

  if (selectedToken && audit) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="light" />
        <View style={styles.auditHeader}>
          <TouchableOpacity testID="audit-back-btn" onPress={() => { setSelectedToken(null); setAudit(null); }}>
            <Text style={styles.backBtn}>{'< BACK'}</Text>
          </TouchableOpacity>
          <Text style={styles.auditTitle}>SAFETY AUDIT</Text>
        </View>

        <View style={styles.scoreContainer}>
          <View style={[styles.scoreRing, {
            borderColor: audit.safety_score >= 80 ? C.success : audit.safety_score >= 50 ? C.warning : C.danger,
          }]}>
            <Text style={[styles.scoreValue, {
              color: audit.safety_score >= 80 ? C.success : audit.safety_score >= 50 ? C.warning : C.danger,
            }]}>{audit.safety_score}</Text>
            <Text style={styles.scoreLabel}>/ 100</Text>
          </View>
          <Text style={[styles.scoreBadge, {
            color: audit.safety_passed ? C.success : C.danger,
          }]}>
            {audit.safety_passed ? 'PASSED' : 'FAILED'}
          </Text>
        </View>

        <View style={styles.tokenInfo}>
          <Text style={styles.tokenName}>{audit.token_name}</Text>
          <View style={[styles.platformBadge, { borderColor: platformColor(audit.platform) }]}>
            <Text style={[styles.platformText, { color: platformColor(audit.platform) }]}>{audit.platform}</Text>
          </View>
        </View>

        <View style={styles.mintBlock}>
          <Text style={styles.mintLabel}>CONTRACT</Text>
          <Text style={styles.mintAddr} numberOfLines={2}>{audit.token_mint}</Text>
        </View>

        <Text style={styles.checklistTitle}>7-POINT CHECKLIST</Text>
        <View style={styles.checklist}>
          <CheckRow label="Mint Authority Revoked" passed={audit.checks?.mint_revoked} />
          <CheckRow label="Freeze Authority Revoked" passed={audit.checks?.freeze_revoked} />
          <CheckRow label="Update Authority Revoked" passed={audit.checks?.update_revoked} />
          <CheckRow label="LP Burned" passed={audit.checks?.lp_burned} />
          <CheckRow label={`Top Holder: ${audit.checks?.top_holder_pct}%`} passed={audit.checks?.top_holder_pct <= 15} />
          <CheckRow label="No Bundled Launch" passed={!audit.checks?.bundled} />
          <CheckRow label="Social Links" passed={audit.checks?.social_links} />
        </View>

        <View style={styles.mcapBlock}>
          <Text style={styles.mcapLabel}>MARKET CAP</Text>
          <Text style={styles.mcapValue}>${audit.market_cap_usd?.toLocaleString()}</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Radar color={C.primary} size={22} />
          <Text style={styles.headerTitle}>SCANNER</Text>
        </View>
        <TouchableOpacity
          testID="simulate-detection-btn"
          style={styles.simBtn}
          onPress={simulateDetection}
          disabled={simulating}
        >
          {simulating ? (
            <ActivityIndicator size="small" color={C.primary} />
          ) : (
            <Text style={styles.simBtnText}>+ SIMULATE</Text>
          )}
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={C.primary} />
        </View>
      ) : feed.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Radar color={C.muted} size={48} strokeWidth={1} />
          <Text style={styles.emptyText}>NO DETECTIONS YET</Text>
          <Text style={styles.emptySubText}>Start the bot or simulate a detection</Text>
        </View>
      ) : (
        <FlatList
          data={feed}
          keyExtractor={(item) => item.id}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchFeed(); }} tintColor={C.primary} />
          }
          renderItem={({ item }) => (
            <TouchableOpacity
              testID={`token-row-${item.id}`}
              style={styles.tokenRow}
              onPress={() => viewAudit(item)}
              activeOpacity={0.7}
            >
              <View style={styles.tokenRowLeft}>
                {item.safety_passed ? (
                  <ShieldCheck color={C.success} size={20} />
                ) : (
                  <ShieldAlert color={C.danger} size={20} />
                )}
                <View style={styles.tokenRowInfo}>
                  <Text style={styles.tokenRowName}>{item.token_name}</Text>
                  <Text style={styles.tokenRowMint}>{item.token_mint?.slice(0, 16)}...</Text>
                </View>
              </View>
              <View style={styles.tokenRowRight}>
                <View style={[styles.platformPill, { borderColor: platformColor(item.platform) }]}>
                  <Text style={[styles.platformPillText, { color: platformColor(item.platform) }]}>
                    {item.platform}
                  </Text>
                </View>
                <View style={styles.tokenMeta}>
                  <Text style={[styles.scoreText, {
                    color: item.safety_score >= 80 ? C.success : item.safety_score >= 50 ? C.warning : C.danger,
                  }]}>{item.safety_score}/100</Text>
                  <View style={[styles.actionPill, {
                    backgroundColor: item.action === 'sniped' ? C.successBg : C.dangerBg,
                    borderColor: item.action === 'sniped' ? C.success : C.danger,
                  }]}>
                    <Text style={[styles.actionText, {
                      color: item.action === 'sniped' ? C.success : C.danger,
                    }]}>{item.action === 'sniped' ? 'SNIPED' : 'REJECTED'}</Text>
                  </View>
                </View>
              </View>
            </TouchableOpacity>
          )}
          contentContainerStyle={{ paddingBottom: 32 }}
        />
      )}
    </SafeAreaView>
  );
}

function CheckRow({ label, passed }: { label: string; passed: boolean }) {
  return (
    <View style={styles.checkRow}>
      <View style={[styles.checkIcon, { backgroundColor: passed ? C.successBg : C.dangerBg, borderColor: passed ? C.success : C.danger }]}>
        <Text style={{ color: passed ? C.success : C.danger, fontSize: 12, fontWeight: '800' }}>
          {passed ? '✓' : '✗'}
        </Text>
      </View>
      <Text style={[styles.checkLabel, { color: passed ? C.textSec : C.danger }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#030206' },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 20, paddingTop: 12, paddingBottom: 12,
    borderBottomWidth: 1, borderBottomColor: '#321B4D',
  },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  headerTitle: { color: '#F4F0FF', fontSize: 22, fontWeight: '800', letterSpacing: 2 },
  simBtn: {
    paddingHorizontal: 14, paddingVertical: 8, borderWidth: 1,
    borderColor: C.primary, borderRadius: 4, backgroundColor: 'rgba(157, 76, 221, 0.4)',
  },
  simBtnText: { color: C.primary, fontSize: 11, fontWeight: '700', letterSpacing: 1 },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  emptyText: { color: C.muted, fontSize: 14, fontWeight: '700', letterSpacing: 3 },
  emptySubText: { color: '#5C4A7A', fontSize: 12 },

  tokenRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 14,
    borderBottomWidth: 1, borderBottomColor: '#1A1025',
  },
  tokenRowLeft: { flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1 },
  tokenRowInfo: { flex: 1 },
  tokenRowName: { color: '#F4F0FF', fontSize: 15, fontWeight: '700' },
  tokenRowMint: { color: '#5C4A7A', fontSize: 10, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', marginTop: 2 },
  tokenRowRight: { alignItems: 'flex-end', gap: 6 },
  platformPill: { paddingHorizontal: 8, paddingVertical: 2, borderWidth: 1, borderRadius: 3 },
  platformPillText: { fontSize: 9, fontWeight: '700', letterSpacing: 1 },
  tokenMeta: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  scoreText: { fontSize: 12, fontWeight: '800' },
  actionPill: { paddingHorizontal: 6, paddingVertical: 2, borderWidth: 1, borderRadius: 2 },
  actionText: { fontSize: 8, fontWeight: '800', letterSpacing: 1 },

  // Audit view
  auditHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 16,
    paddingHorizontal: 20, paddingTop: 12, paddingBottom: 12,
    borderBottomWidth: 1, borderBottomColor: '#321B4D',
  },
  backBtn: { color: C.primary, fontSize: 14, fontWeight: '700' },
  auditTitle: { color: '#F4F0FF', fontSize: 20, fontWeight: '800', letterSpacing: 2 },

  scoreContainer: { alignItems: 'center', paddingVertical: 32 },
  scoreRing: {
    width: 120, height: 120, borderRadius: 60, borderWidth: 3,
    justifyContent: 'center', alignItems: 'center', backgroundColor: '#0D0814',
  },
  scoreValue: { fontSize: 42, fontWeight: '900' },
  scoreLabel: { color: '#5C4A7A', fontSize: 14 },
  scoreBadge: { fontSize: 16, fontWeight: '800', letterSpacing: 4, marginTop: 12 },

  tokenInfo: {
    flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 12, marginBottom: 20,
  },
  tokenName: { color: '#F4F0FF', fontSize: 22, fontWeight: '800' },
  platformBadge: { paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderRadius: 4 },
  platformText: { fontSize: 11, fontWeight: '700', letterSpacing: 1 },

  mintBlock: {
    marginHorizontal: 20, marginBottom: 20, backgroundColor: '#0D0814',
    borderWidth: 1, borderColor: '#321B4D', borderRadius: 4, padding: 12,
  },
  mintLabel: { color: '#5C4A7A', fontSize: 9, fontWeight: '700', letterSpacing: 3, marginBottom: 6 },
  mintAddr: { color: '#A390C2', fontSize: 11, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },

  checklistTitle: {
    color: '#5C4A7A', fontSize: 10, fontWeight: '700', letterSpacing: 3,
    paddingHorizontal: 20, marginBottom: 12,
  },
  checklist: { paddingHorizontal: 20, gap: 8 },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  checkIcon: {
    width: 24, height: 24, borderRadius: 12, borderWidth: 1,
    justifyContent: 'center', alignItems: 'center',
  },
  checkLabel: { fontSize: 13 },

  mcapBlock: {
    marginHorizontal: 20, marginTop: 24, backgroundColor: '#0D0814',
    borderWidth: 1, borderColor: '#321B4D', borderRadius: 4, padding: 12,
  },
  mcapLabel: { color: '#5C4A7A', fontSize: 9, fontWeight: '700', letterSpacing: 3, marginBottom: 4 },
  mcapValue: { color: '#F4F0FF', fontSize: 24, fontWeight: '800' },
});
