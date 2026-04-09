import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  RefreshControl, ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { Zap, ZapOff, Activity, TrendingUp, Target, Eye, LogOut, Crown, Radar } from 'lucide-react-native';
import { useAuth } from '../src/AuthContext';

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
  const { user, logout } = useAuth();
  const [state, setState] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [wallet, setWallet] = useState<any>(null);
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [stateRes, statsRes, walletRes, configRes] = await Promise.all([
        fetch(`${API}/api/bot/state`),
        fetch(`${API}/api/stats`),
        fetch(`${API}/api/wallet`),
        fetch(`${API}/api/bot/config`),
      ]);
      setState(await stateRes.json());
      setStats(await statsRes.json());
      setWallet(await walletRes.json());
      setConfig(await configRes.json());
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
      await fetchData();
    } catch (e) {
      console.error('Toggle error:', e);
    } finally {
      setToggling(false);
    }
  };

  const toggleScanner = async () => {
    try {
      const newState = !state?.scanner_running;
      await fetch(`${API}/api/bot/state`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scanner_running: newState }),
      });
      await fetchData();
    } catch (e) {
      console.error('Toggle scanner error:', e);
    }
  };

  const toggleAutoBuy = async () => {
    try {
      const newAutoBuy = !config?.auto_buy;
      await fetch(`${API}/api/bot/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_buy: newAutoBuy }),
      });
      await fetchData();
    } catch (e) {
      console.error('Toggle auto-buy error:', e);
    }
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
  // Bot and scanner states accessed via state?.is_running and state?.scanner_running

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
          <View>
            <Text style={styles.title}>SOLANA SNIPER</Text>
            {user && (
              <Text style={styles.userEmail}>{user.email}</Text>
            )}
          </View>
          <View style={styles.headerRight}>
            {user?.subscription?.status === 'active' && (
              <View style={styles.premiumBadge}>
                <Crown color="#FFD700" size={12} />
                <Text style={styles.premiumText}>PRO</Text>
              </View>
            )}
            <TouchableOpacity
              testID="mode-toggle-btn"
              style={[styles.modeBadge, config?.auto_buy ? styles.modeLive : styles.modePaper]}
              onPress={toggleAutoBuy}
            >
              <Text style={[styles.modeText, config?.auto_buy ? styles.modeTextLive : styles.modeTextPaper]}>
                {config?.auto_buy ? 'AUTO-BUY' : 'ALERT'}
              </Text>
            </TouchableOpacity>
            {user && (
              <TouchableOpacity testID="logout-btn" style={styles.logoutBtn} onPress={logout}>
                <LogOut color={C.muted} size={18} />
              </TouchableOpacity>
            )}
          </View>
        </View>

        {/* Dual Control Buttons */}
        <View style={styles.dualBtnContainer}>
          {/* Bot Toggle */}
          <TouchableOpacity
            testID="dashboard-start-bot-button"
            style={[
              styles.dualBtn,
              state?.is_running ? styles.dualBtnActiveGreen : styles.dualBtnInactive,
            ]}
            onPress={toggleBot}
            disabled={toggling}
            activeOpacity={0.7}
          >
            {toggling ? (
              <ActivityIndicator size="small" color={state?.is_running ? C.success : C.primary} />
            ) : state?.is_running ? (
              <Zap color={C.success} size={28} strokeWidth={2} />
            ) : (
              <ZapOff color={C.muted} size={28} strokeWidth={1.5} />
            )}
            <Text style={[styles.dualBtnLabel, state?.is_running && styles.dualBtnLabelActive]}>
              {state?.is_running ? 'BOT ON' : 'BOT OFF'}
            </Text>
          </TouchableOpacity>

          {/* Scanner Toggle */}
          <TouchableOpacity
            testID="dashboard-start-scanner-button"
            style={[
              styles.dualBtn,
              state?.scanner_running ? styles.dualBtnActivePurple : styles.dualBtnInactive,
            ]}
            onPress={toggleScanner}
            activeOpacity={0.7}
          >
            {state?.scanner_running ? (
              <Radar color={C.primary} size={28} strokeWidth={2} />
            ) : (
              <Radar color={C.muted} size={28} strokeWidth={1.5} />
            )}
            <Text style={[styles.dualBtnLabel, state?.scanner_running && { color: C.primary }]}>
              {state?.scanner_running ? 'SCANNING' : 'SCAN OFF'}
            </Text>
          </TouchableOpacity>
        </View>
        {state?.started_at && (
          <Text style={styles.uptimeText}>
            SCANNER ONLINE SINCE {new Date(state.started_at).toLocaleTimeString()}
          </Text>
        )}

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
            <View style={[styles.statusDot, { backgroundColor: state?.is_running ? C.success : C.danger }]} />
            <Text style={styles.statusText}>
              {state?.is_running ? 'Bot Active (Trading)' : 'Bot Offline'}
            </Text>
          </View>
          <View style={styles.statusRow}>
            <View style={[styles.statusDot, { backgroundColor: state?.scanner_running ? C.success : C.danger }]} />
            <Text style={styles.statusText}>
              {state?.scanner_running ? 'Scanner Active' : 'Scanner Offline'}
            </Text>
          </View>
          <View style={styles.statusRow}>
            <View style={[styles.statusDot, { backgroundColor: config?.auto_buy ? C.success : C.warning }]} />
            <Text style={styles.statusText}>
              {config?.auto_buy ? 'Auto-Buy Active' : 'Alert Only Mode'}
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
  title: { color: C.text, fontSize: 24, fontWeight: '800', letterSpacing: 2 },
  userEmail: { color: C.muted, fontSize: 10, marginTop: 2 },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  premiumBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 4, borderRadius: 3,
    borderWidth: 1, borderColor: '#FFD700', backgroundColor: 'rgba(255,215,0,0.1)',
  },
  premiumText: { color: '#FFD700', fontSize: 9, fontWeight: '800', letterSpacing: 1 },
  logoutBtn: {
    width: 36, height: 36, borderRadius: 4, borderWidth: 1, borderColor: C.border,
    justifyContent: 'center', alignItems: 'center',
  },
  modeBadge: {
    paddingHorizontal: 14, paddingVertical: 6, borderRadius: 4, borderWidth: 1,
  },
  modePaper: { borderColor: C.warning, backgroundColor: 'rgba(255,215,0,0.1)' },
  modeLive: { borderColor: C.success, backgroundColor: 'rgba(57,255,20,0.1)' },
  modeText: { fontSize: 11, fontWeight: '700', letterSpacing: 2 },
  modeTextPaper: { color: C.warning },
  modeTextLive: { color: C.success },

  dualBtnContainer: {
    flexDirection: 'row', paddingHorizontal: 20, gap: 14, paddingVertical: 24,
  },
  dualBtn: {
    flex: 1, height: 110, borderRadius: 12, borderWidth: 2,
    justifyContent: 'center', alignItems: 'center', gap: 10,
  },
  dualBtnInactive: {
    borderColor: C.border, backgroundColor: C.surface,
  },
  dualBtnActiveGreen: {
    borderColor: C.success, backgroundColor: 'rgba(57, 255, 20, 0.08)',
    ...(Platform.OS === 'android' ? { elevation: 8 } : {}),
  },
  dualBtnActivePurple: {
    borderColor: C.primary, backgroundColor: 'rgba(157, 76, 221, 0.08)',
    ...(Platform.OS === 'android' ? { elevation: 8 } : {}),
  },
  dualBtnLabel: {
    color: C.muted, fontSize: 13, fontWeight: '800', letterSpacing: 3,
  },
  dualBtnLabelActive: { color: C.success },
  uptimeText: { color: C.muted, fontSize: 10, letterSpacing: 2, textAlign: 'center', marginBottom: 8 },

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
