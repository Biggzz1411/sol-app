import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, Switch, ActivityIndicator, Platform, KeyboardAvoidingView,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { Settings, Save, RotateCcw } from 'lucide-react-native';

const API = process.env.EXPO_PUBLIC_BACKEND_URL;

const C = {
  bg: '#030206',
  surface: '#0D0814',
  surfaceHi: '#1A1025',
  border: '#321B4D',
  primary: '#9D4CDD',
  primaryGlow: 'rgba(157, 76, 221, 0.4)',
  success: '#39FF14',
  danger: '#FF2A2A',
  warning: '#FFD700',
  text: '#F4F0FF',
  textSec: '#A390C2',
  muted: '#5C4A7A',
};

export default function ConfigScreen() {
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/bot/config`);
      const data = await res.json();
      setConfig(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const saveConfig = async () => {
    setSaving(true);
    try {
      await fetch(`${API}/api/bot/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const resetAll = async () => {
    try {
      await fetch(`${API}/api/reset`, { method: 'POST' });
      await fetchConfig();
    } catch (e) {
      console.error(e);
    }
  };

  const updateField = (key: string, value: any) => {
    setConfig((prev: any) => ({ ...prev, [key]: value }));
  };

  if (loading || !config) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="light" />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={C.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <Settings color={C.primary} size={22} />
            <Text style={styles.headerTitle}>CONFIG</Text>
          </View>
          <View style={styles.headerActions}>
            <TouchableOpacity testID="reset-all-btn" style={styles.resetBtn} onPress={resetAll}>
              <RotateCcw color={C.danger} size={16} />
            </TouchableOpacity>
            <TouchableOpacity testID="save-config-btn" style={styles.saveBtn} onPress={saveConfig} disabled={saving}>
              {saving ? (
                <ActivityIndicator size="small" color={C.primary} />
              ) : (
                <>
                  <Save color={C.primary} size={16} />
                  <Text style={styles.saveBtnText}>SAVE</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </View>

        <ScrollView
          style={styles.scroll}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchConfig(); }} tintColor={C.primary} />
          }
        >
          {/* Strategy */}
          <Text style={styles.sectionTitle}>STRATEGY</Text>
          <View style={styles.segmentRow}>
            {['aggressive', 'balanced', 'safe'].map(s => (
              <TouchableOpacity
                key={s}
                testID={`strategy-${s}-btn`}
                style={[styles.segmentBtn, config.strategy === s && styles.segmentActive]}
                onPress={() => updateField('strategy', s)}
              >
                <Text style={[styles.segmentText, config.strategy === s && styles.segmentTextActive]}>
                  {s.toUpperCase()}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Buy Settings */}
          <Text style={styles.sectionTitle}>BUY SETTINGS</Text>
          <View style={styles.card}>
            <NumberInput label="Buy Amount (SOL)" value={config.buy_amount_sol} onChange={(v) => updateField('buy_amount_sol', v)} step={0.01} testId="config-buy-amount" />
            <NumberInput label="Slippage (bps)" value={config.slippage_bps} onChange={(v) => updateField('slippage_bps', v)} step={100} isInt testId="config-slippage-input" />
            <NumberInput label="Priority Fee (lamports)" value={config.priority_fee_lamports} onChange={(v) => updateField('priority_fee_lamports', v)} step={1000} isInt testId="config-priority-fee" />
            <NumberInput label="Jito Tip (SOL)" value={config.jito_tip_sol} onChange={(v) => updateField('jito_tip_sol', v)} step={0.005} testId="config-jito-tip" />
            <NumberInput label="Max Open Positions" value={config.max_open_positions} onChange={(v) => updateField('max_open_positions', v)} step={1} isInt testId="config-max-positions" />
            <ToggleRow label="Use Jito Bundles" value={config.use_jito} onChange={(v) => updateField('use_jito', v)} testId="config-use-jito" />
          </View>

          {/* Sell Settings */}
          <Text style={styles.sectionTitle}>SELL SETTINGS</Text>
          <View style={styles.card}>
            <ToggleRow label="Auto Sell" value={config.auto_sell} onChange={(v) => updateField('auto_sell', v)} testId="config-auto-sell" />
            <NumberInput label="Take Profit 1 (%)" value={config.take_profit_pct1} onChange={(v) => updateField('take_profit_pct1', v)} step={10} isInt testId="config-tp1" />
            <NumberInput label="Take Profit 2 (%)" value={config.take_profit_pct2} onChange={(v) => updateField('take_profit_pct2', v)} step={50} isInt testId="config-tp2" />
            <NumberInput label="Stop Loss (%)" value={config.stop_loss_pct} onChange={(v) => updateField('stop_loss_pct', v)} step={5} isInt testId="config-sl" />
            <NumberInput label="Trailing Stop (%)" value={config.trailing_stop_pct} onChange={(v) => updateField('trailing_stop_pct', v)} step={5} isInt testId="config-trailing" />
            <NumberInput label="Max Hold (seconds)" value={config.max_hold_seconds} onChange={(v) => updateField('max_hold_seconds', v)} step={300} isInt testId="config-max-hold" />
          </View>

          {/* Safety Filters */}
          <Text style={styles.sectionTitle}>SAFETY FILTERS</Text>
          <View style={styles.card}>
            <ToggleRow label="Require Mint Revoked" value={config.require_mint_revoked} onChange={(v) => updateField('require_mint_revoked', v)} testId="config-mint-revoked" />
            <ToggleRow label="Require Freeze Revoked" value={config.require_freeze_revoked} onChange={(v) => updateField('require_freeze_revoked', v)} testId="config-freeze-revoked" />
            <ToggleRow label="Require Update Revoked" value={config.require_update_revoked} onChange={(v) => updateField('require_update_revoked', v)} testId="config-update-revoked" />
            <ToggleRow label="Require LP Burned" value={config.require_lp_burned} onChange={(v) => updateField('require_lp_burned', v)} testId="config-lp-burned" />
            <ToggleRow label="Reject Bundled Launches" value={config.reject_bundles} onChange={(v) => updateField('reject_bundles', v)} testId="config-reject-bundles" />
            <NumberInput label="Max Top Holder (%)" value={config.max_top_holder_pct} onChange={(v) => updateField('max_top_holder_pct', v)} step={1} isInt testId="config-max-holder" />
            <NumberInput label="Min Market Cap ($)" value={config.min_market_cap_usd} onChange={(v) => updateField('min_market_cap_usd', v)} step={1000} isInt testId="config-min-mcap" />
            <NumberInput label="Min Safety Score" value={config.min_safety_score} onChange={(v) => updateField('min_safety_score', v)} step={5} isInt testId="config-min-score" />
          </View>

          {/* Platforms */}
          <Text style={styles.sectionTitle}>PLATFORMS</Text>
          <View style={styles.card}>
            <ToggleRow label="Pump.fun" value={config.platform_pumpfun} onChange={(v) => updateField('platform_pumpfun', v)} testId="config-platform-pumpfun" dotColor="#39FF14" />
            <ToggleRow label="Raydium" value={config.platform_raydium} onChange={(v) => updateField('platform_raydium', v)} testId="config-platform-raydium" dotColor="#5E17EB" />
            <ToggleRow label="PumpSwap" value={config.platform_pumpswap} onChange={(v) => updateField('platform_pumpswap', v)} testId="config-platform-pumpswap" dotColor="#FF8C00" />
          </View>

          <View style={{ height: 48 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function NumberInput({ label, value, onChange, step = 1, isInt = false, testId }: any) {
  const adjust = (dir: number) => {
    const newVal = isInt ? Math.round(value + step * dir) : parseFloat((value + step * dir).toFixed(4));
    onChange(newVal);
  };

  return (
    <View style={styles.inputRow}>
      <Text style={styles.inputLabel}>{label}</Text>
      <View style={styles.inputControls}>
        <TouchableOpacity testID={`${testId}-minus`} style={styles.adjBtn} onPress={() => adjust(-1)}>
          <Text style={styles.adjBtnText}>-</Text>
        </TouchableOpacity>
        <TextInput
          testID={testId}
          style={styles.numberInput}
          value={String(value)}
          keyboardType="numeric"
          onChangeText={(t) => {
            const n = isInt ? parseInt(t) || 0 : parseFloat(t) || 0;
            onChange(n);
          }}
          placeholderTextColor="#5C4A7A"
        />
        <TouchableOpacity testID={`${testId}-plus`} style={styles.adjBtn} onPress={() => adjust(1)}>
          <Text style={styles.adjBtnText}>+</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

function ToggleRow({ label, value, onChange, testId, dotColor }: any) {
  return (
    <View style={styles.toggleRow}>
      <View style={styles.toggleLabelRow}>
        {dotColor && <View style={[styles.platformDot, { backgroundColor: dotColor }]} />}
        <Text style={styles.toggleLabel}>{label}</Text>
      </View>
      <Switch
        testID={testId}
        value={value}
        onValueChange={onChange}
        trackColor={{ false: '#1A1025', true: 'rgba(157, 76, 221, 0.4)' }}
        thumbColor={value ? '#9D4CDD' : '#5C4A7A'}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#030206' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  scroll: { flex: 1 },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 20, paddingTop: 12, paddingBottom: 12,
    borderBottomWidth: 1, borderBottomColor: '#321B4D',
  },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  headerTitle: { color: '#F4F0FF', fontSize: 22, fontWeight: '800', letterSpacing: 2 },
  headerActions: { flexDirection: 'row', gap: 10 },
  resetBtn: {
    width: 40, height: 40, borderRadius: 4, borderWidth: 1, borderColor: '#FF2A2A',
    backgroundColor: 'rgba(255,42,42,0.1)', justifyContent: 'center', alignItems: 'center',
  },
  saveBtn: {
    flexDirection: 'row', gap: 6, paddingHorizontal: 16, paddingVertical: 10,
    borderWidth: 1, borderColor: '#9D4CDD', borderRadius: 4,
    backgroundColor: 'rgba(157, 76, 221, 0.15)', alignItems: 'center',
  },
  saveBtnText: { color: '#9D4CDD', fontSize: 12, fontWeight: '700', letterSpacing: 1 },

  sectionTitle: {
    color: '#5C4A7A', fontSize: 10, fontWeight: '700', letterSpacing: 3,
    paddingHorizontal: 20, marginTop: 20, marginBottom: 10,
  },
  segmentRow: {
    flexDirection: 'row', paddingHorizontal: 16, gap: 8, marginBottom: 8,
  },
  segmentBtn: {
    flex: 1, paddingVertical: 12, alignItems: 'center',
    borderWidth: 1, borderColor: '#321B4D', borderRadius: 4,
    backgroundColor: '#0D0814',
  },
  segmentActive: {
    borderColor: '#9D4CDD', backgroundColor: 'rgba(157, 76, 221, 0.15)',
  },
  segmentText: { color: '#5C4A7A', fontSize: 12, fontWeight: '700', letterSpacing: 2 },
  segmentTextActive: { color: '#9D4CDD' },

  card: {
    marginHorizontal: 16, backgroundColor: '#0D0814',
    borderWidth: 1, borderColor: '#321B4D', borderRadius: 6, padding: 14,
  },

  inputRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#1A1025',
  },
  inputLabel: { color: '#A390C2', fontSize: 13, flex: 1 },
  inputControls: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  adjBtn: {
    width: 32, height: 32, borderRadius: 4, borderWidth: 1, borderColor: '#321B4D',
    backgroundColor: '#1A1025', justifyContent: 'center', alignItems: 'center',
  },
  adjBtnText: { color: '#9D4CDD', fontSize: 18, fontWeight: '700' },
  numberInput: {
    width: 80, height: 32, borderRadius: 4, borderWidth: 1, borderColor: '#321B4D',
    backgroundColor: '#1A1025', color: '#F4F0FF', textAlign: 'center', fontSize: 13,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },

  toggleRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#1A1025',
  },
  toggleLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  toggleLabel: { color: '#A390C2', fontSize: 13 },
  platformDot: { width: 8, height: 8, borderRadius: 4 },
});
