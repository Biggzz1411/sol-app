import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  RefreshControl, ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { Zap, ZapOff, Activity, TrendingUp, Target, Eye } from 'lucide-react-native';

const API = process.env.EXPO_PUBLIC_BACKEND_URL;

const C = {
  bg: '#030206',
  surface: '#0D0814',
  surfaceHi: '#1A1025',
  border: '#321B4D',
  primary: '#9D4CDD',
  primaryGlow: 'rgba(157, 76, 221, 0.4)',
  success: '#39FF14',
  successBg: 'rgba(57, 255, 20, 0.1)',
  danger: '#FF2A2A',
  dangerBg: 'rgba(255, 42, 42, 0.1)',
  warning: '#FFD700',
  text: '#F4F0FF',
  textSec: '#A390C2',
  muted: '#5C4A7A',
};

export default function Dashboard() {
  const [state, setState] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [wallet, setWallet] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [stateRes, statsRes, walletRes] = await Promise.all([
        fetch(`${API}/api/bot/state`),
        fetch(`${API}/api/stats`),
        fetch(`${API}/api/wallet`),
      ]);
      setState(await stateRes.json());
      setStats(await statsRes.json());
      setWallet(await walletRes.json());
    } catch (e) {
      console.error('Fetch error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const toggleBot = async () => {
    setToggling(true);
    try {
      const newState = !state?.is_running;
      await fetch(`${API}/api/bot/state`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_running: newState }),
      });

      // If starting, simulate some detections
      if (newState) {
        for (let i = 0; i < 3; i++) {
          setTimeout(async () => {
            await fetch(`${API}/api/scanner/simulate`, { method: 'POST' });
          }, (i + 1) * 2000);
        }
      }
      await fetchData();
    } catch (e) {
      console.error('Toggle error:', e);
    } finally {
      setToggling(false);
    }
  };

  const toggleMode = async () => {
    const newMode = state?.mode === 'paper' ? 'live' : 'paper';
    await fetch(`${API}/api/bot/state`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: newMode }),
    });
    await fetchData();
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="light" />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={C.primary} />
          <Text style={styles.loadingText}>INITIALIZING...</Text>
        </View>
      </SafeAreaView>
    );
  }

  const isRunning = state?.is_running;
  const mode = state?.mode || 'paper';

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <ScrollView
        style={styles.scroll}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchData(); }} tintColor={C.primary} />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>SOLANA SNIPER</Text>
          <TouchableOpacity
            testID="mode-toggle-btn"
            style={[styles.modeBadge, mode === 'live' ? styles.modeLive : styles.modePaper]}
            onPress={toggleMode}
          >
            <Text style={[styles.modeText, mode === 'live' ? styles.modeTextLive : styles.modeTextPaper]}>
              {mode === 'paper' ? 'PAPER' : 'LIVE'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Reactor Button */}
        <View style={styles.reactorContainer}>
          <TouchableOpacity
            testID="dashboard-start-bot-button"
            style={[
              styles.reactorBtn,
              isRunning ? styles.reactorActive : styles.reactorInactive,
            ]}
            onPress={toggleBot}
            disabled={toggling}
            activeOpacity={0.7}
          >
            {toggling ? (
              <ActivityIndicator size="large" color={isRunning ? C.success : C.primary} />
            ) : isRunning ? (
              <Zap color={C.success} size={48} strokeWidth={2} />
            ) : (
              <ZapOff color={C.muted} size={48} strokeWidth={1.5} />
            )}
          </TouchableOpacity>
          <Text style={[styles.reactorLabel, isRunning && styles.reactorLabelActive]}>
            {toggling ? 'PROCESSING...' : isRunning ? 'SYSTEM ACTIVE' : 'TAP TO ENGAGE'}
          </Text>
          {isRunning && state?.started_at && (
            <Text style={styles.uptimeText}>
              ONLINE SINCE {new Date(state.started_at).toLocaleTimeString()}
            </Text>
          )}
        </View>

        {/* Stats Grid */}
        <View style={styles.statsGrid}>
          <StatBlock icon={<Eye color={C.primary} size={18} />} label="SCANNED" value={stats?.tokens_scanned || 0} />
          <StatBlock icon={<Target color={C.success} size={18} />} label="SNIPED" value={stats?.tokens_sniped || 0} />
          <StatBlock icon={<Activity color={C.warning} size={18} />} label="OPEN" value={stats?.open_positions || 0} />
          <StatBlock icon={<TrendingUp color={C.textSec} size={18} />} label="CLOSED" value={stats?.closed_positions || 0} />
        </View>

        {/* Wallet Card */}
        <View style={styles.card}>
          <Text style={styles.cardLabel}>WALLET</Text>
          <Text style={styles.walletBalance}>
            {wallet?.balance_sol?.toFixed(4) || '0.0000'} <Text style={styles.solUnit}>SOL</Text>
          </Text>
          <Text style={styles.walletAddr} numberOfLines={1}>
            {wallet?.address?.slice(0, 20) || 'Not connected'}...
          </Text>
        </View>

        {/* Quick Info */}
        <View style={styles.card}>
          <Text style={styles.cardLabel}>STATUS</Text>
          <View style={styles.statusRow}>
            <View style={[styles.statusDot, { backgroundColor: isRunning ? C.success : C.danger }]} />
            <Text style={styles.statusText}>
              {isRunning ? 'Scanner Active' : 'Scanner Offline'}
            </Text>
          </View>
          <View style={styles.statusRow}>
            <View style={[styles.statusDot, { backgroundColor: mode === 'paper' ? C.warning : C.danger }]} />
            <Text style={styles.statusText}>
              {mode === 'paper' ? 'Paper Trade Mode' : 'Live Trading Mode'}
            </Text>
          </View>
          <View style={styles.statusRow}>
            <View style={[styles.statusDot, { backgroundColor: C.primary }]} />
            <Text style={styles.statusText}>
              Platforms: pump.fun, raydium, pumpswap
            </Text>
          </View>
        </View>

        <View style={{ height: 32 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function StatBlock({ icon, label, value }: { icon: React.ReactNode; label: string; value: number | string }) {
  return (
    <View style={styles.statBlock}>
      {icon}
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bg },
  scroll: { flex: 1 },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 16 },
  loadingText: { color: C.muted, fontSize: 12, letterSpacing: 4 },

  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 20, paddingTop: 12, paddingBottom: 8,
  },
  title: { color: C.text, fontSize: 28, fontWeight: '800', letterSpacing: 2 },
  modeBadge: {
    paddingHorizontal: 14, paddingVertical: 6, borderRadius: 4, borderWidth: 1,
  },
  modePaper: { borderColor: C.warning, backgroundColor: 'rgba(255,215,0,0.1)' },
  modeLive: { borderColor: C.danger, backgroundColor: C.dangerBg },
  modeText: { fontSize: 11, fontWeight: '700', letterSpacing: 2 },
  modeTextPaper: { color: C.warning },
  modeTextLive: { color: C.danger },

  reactorContainer: { alignItems: 'center', paddingVertical: 32 },
  reactorBtn: {
    width: 140, height: 140, borderRadius: 70, justifyContent: 'center', alignItems: 'center',
    borderWidth: 2,
  },
  reactorInactive: {
    borderColor: C.border, backgroundColor: C.surface,
  },
  reactorActive: {
    borderColor: C.success, backgroundColor: 'rgba(57, 255, 20, 0.08)',
    shadowColor: C.success, shadowOffset: { width: 0, height: 0 }, shadowOpacity: 0.6, shadowRadius: 30,
    ...(Platform.OS === 'android' ? { elevation: 12 } : {}),
  },
  reactorLabel: {
    marginTop: 16, color: C.muted, fontSize: 13, fontWeight: '700', letterSpacing: 3,
  },
  reactorLabelActive: { color: C.success },
  uptimeText: { color: C.muted, fontSize: 10, letterSpacing: 2, marginTop: 4 },

  statsGrid: {
    flexDirection: 'row', paddingHorizontal: 16, gap: 10, marginBottom: 16,
  },
  statBlock: {
    flex: 1, backgroundColor: C.surface, borderWidth: 1, borderColor: C.border,
    borderRadius: 6, padding: 14, alignItems: 'center', gap: 6,
  },
  statValue: { color: C.text, fontSize: 24, fontWeight: '800' },
  statLabel: { color: C.muted, fontSize: 9, fontWeight: '600', letterSpacing: 2 },

  card: {
    marginHorizontal: 16, marginBottom: 12, backgroundColor: C.surface,
    borderWidth: 1, borderColor: C.border, borderRadius: 6, padding: 16,
  },
  cardLabel: { color: C.muted, fontSize: 10, fontWeight: '700', letterSpacing: 3, marginBottom: 10 },
  walletBalance: { color: C.text, fontSize: 32, fontWeight: '800' },
  solUnit: { color: C.primary, fontSize: 18 },
  walletAddr: { color: C.muted, fontSize: 11, marginTop: 4, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },

  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { color: C.textSec, fontSize: 13 },
});
