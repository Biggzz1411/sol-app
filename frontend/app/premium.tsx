import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Platform, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { useAuth } from '../src/AuthContext';
import { useLocalSearchParams } from 'expo-router';
import { Crown, Check, Zap, Shield, Wallet, Bell, Gauge } from 'lucide-react-native';

const API = process.env.EXPO_PUBLIC_BACKEND_URL;

const C = {
  bg: '#030206', surface: '#0D0814', border: '#321B4D',
  primary: '#9D4CDD', success: '#39FF14', danger: '#FF2A2A',
  warning: '#FFD700', gold: '#FFD700', text: '#F4F0FF', textSec: '#A390C2', muted: '#5C4A7A',
};

export default function PremiumScreen() {
  const { user, token, refresh } = useAuth();
  const params = useLocalSearchParams();
  const sessionId = params.session_id as string;
  const [plans, setPlans] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [checkingPayment, setCheckingPayment] = useState(false);
  const [paymentStatus, setPaymentStatus] = useState<string | null>(null);
  const [purchasing, setPurchasing] = useState<string | null>(null);

  const isPremium = user?.is_premium || user?.subscription?.status === 'active';

  useEffect(() => {
    fetchPlans();
  }, []);

  useEffect(() => {
    if (sessionId && token) {
      pollPaymentStatus(sessionId, 0);
    }
  }, [sessionId, token]);

  const fetchPlans = async () => {
    try {
      const res = await fetch(`${API}/api/premium/plans`);
      setPlans(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const pollPaymentStatus = async (sid: string, attempt: number) => {
    if (attempt >= 5) { setPaymentStatus('timeout'); return; }
    setCheckingPayment(true);
    try {
      const res = await fetch(`${API}/api/premium/status/${sid}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.payment_status === 'paid') {
        setPaymentStatus('paid');
        setCheckingPayment(false);
        await refresh();
        return;
      }
      if (data.status === 'expired') {
        setPaymentStatus('expired');
        setCheckingPayment(false);
        return;
      }
      setTimeout(() => pollPaymentStatus(sid, attempt + 1), 2000);
    } catch {
      setPaymentStatus('error');
      setCheckingPayment(false);
    }
  };

  const handlePurchase = async (planId: string) => {
    if (!token) return;
    setPurchasing(planId);
    try {
      const originUrl = typeof window !== 'undefined' ? window.location.origin : API;
      const res = await fetch(`${API}/api/premium/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ plan_id: planId, origin_url: originUrl }),
      });
      const data = await res.json();
      if (data.url) {
        if (Platform.OS === 'web') {
          window.location.href = data.url;
        } else {
          await Linking.openURL(data.url);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setPurchasing(null);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="light" />
        <View style={styles.centered}><ActivityIndicator size="large" color={C.primary} /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <ScrollView style={styles.scroll}>
        {/* Header */}
        <View style={styles.headerSection}>
          <Crown color={C.gold} size={40} />
          <Text style={styles.headerTitle}>PREMIUM</Text>
          <Text style={styles.headerSubtitle}>UNLOCK FULL POWER</Text>
        </View>

        {/* Payment Status */}
        {checkingPayment && (
          <View style={styles.statusBanner}>
            <ActivityIndicator size="small" color={C.primary} />
            <Text style={styles.statusText}>Verifying payment...</Text>
          </View>
        )}
        {paymentStatus === 'paid' && (
          <View style={[styles.statusBanner, { borderColor: C.success }]}>
            <Check color={C.success} size={20} />
            <Text style={[styles.statusText, { color: C.success }]}>Premium activated!</Text>
          </View>
        )}

        {/* Current Status */}
        {isPremium ? (
          <View style={styles.activeCard}>
            <View style={styles.activeHeader}>
              <Crown color={C.gold} size={24} />
              <Text style={styles.activeTitle}>PREMIUM ACTIVE</Text>
            </View>
            <Text style={styles.activePlan}>{user?.subscription?.plan?.toUpperCase()}</Text>
            {user?.subscription?.expires_at && (
              <Text style={styles.activeExpiry}>
                Expires: {new Date(user.subscription.expires_at).toLocaleDateString()}
              </Text>
            )}
          </View>
        ) : (
          <>
            {/* Feature Comparison */}
            <Text style={styles.sectionTitle}>WHAT YOU GET</Text>
            <View style={styles.featureGrid}>
              <FeatureRow icon={<Wallet color={C.primary} size={18} />} free="1 Wallet" premium="10 Wallets" />
              <FeatureRow icon={<Gauge color={C.primary} size={18} />} free="30s Scan" premium="5s Scan" />
              <FeatureRow icon={<Zap color={C.primary} size={18} />} free="Paper Only" premium="Live Trading" />
              <FeatureRow icon={<Bell color={C.primary} size={18} />} free="In-App Only" premium="Push + In-App" />
              <FeatureRow icon={<Shield color={C.primary} size={18} />} free="2 Positions" premium="20 Positions" />
            </View>

            {/* Plans */}
            <Text style={styles.sectionTitle}>CHOOSE YOUR PLAN</Text>
            {plans?.plans && Object.entries(plans.plans).map(([id, plan]: [string, any]) => (
              <TouchableOpacity
                key={id}
                testID={`plan-${id}-btn`}
                style={styles.planCard}
                onPress={() => handlePurchase(id)}
                disabled={purchasing === id}
                activeOpacity={0.7}
              >
                <View style={styles.planHeader}>
                  <Text style={styles.planLabel}>{plan.label}</Text>
                  {id === 'quarterly' && (
                    <View style={styles.saveBadge}>
                      <Text style={styles.saveText}>SAVE 20%</Text>
                    </View>
                  )}
                </View>
                <View style={styles.planPrice}>
                  <Text style={styles.priceAmount}>${plan.price}</Text>
                  <Text style={styles.pricePeriod}>/ {plan.duration_days} days</Text>
                </View>
                {purchasing === id ? (
                  <ActivityIndicator size="small" color={C.primary} />
                ) : (
                  <Text style={styles.planCta}>UPGRADE NOW</Text>
                )}
              </TouchableOpacity>
            ))}
          </>
        )}

        <View style={{ height: 48 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function FeatureRow({ icon, free, premium }: { icon: React.ReactNode; free: string; premium: string }) {
  return (
    <View style={styles.featureRow}>
      {icon}
      <View style={styles.featureContent}>
        <Text style={styles.featureFree}>{free}</Text>
        <Text style={styles.featureArrow}>{'>'}</Text>
        <Text style={styles.featurePremium}>{premium}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bg },
  scroll: { flex: 1 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },

  headerSection: { alignItems: 'center', paddingVertical: 32 },
  headerTitle: { color: C.gold, fontSize: 32, fontWeight: '900', letterSpacing: 4, marginTop: 12 },
  headerSubtitle: { color: C.muted, fontSize: 10, letterSpacing: 6, marginTop: 4 },

  statusBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 10, marginHorizontal: 16,
    marginBottom: 16, padding: 14, backgroundColor: C.surface, borderWidth: 1,
    borderColor: C.primary, borderRadius: 6,
  },
  statusText: { color: C.textSec, fontSize: 13 },

  activeCard: {
    marginHorizontal: 16, marginBottom: 20, padding: 24,
    backgroundColor: C.surface, borderWidth: 2, borderColor: C.gold, borderRadius: 8,
  },
  activeHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  activeTitle: { color: C.gold, fontSize: 18, fontWeight: '800', letterSpacing: 2 },
  activePlan: { color: C.text, fontSize: 14, fontWeight: '600' },
  activeExpiry: { color: C.muted, fontSize: 12, marginTop: 4 },

  sectionTitle: {
    color: C.muted, fontSize: 10, fontWeight: '700', letterSpacing: 3,
    paddingHorizontal: 20, marginTop: 20, marginBottom: 12,
  },

  featureGrid: { marginHorizontal: 16, gap: 8, marginBottom: 16 },
  featureRow: {
    flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14,
    backgroundColor: C.surface, borderWidth: 1, borderColor: C.border, borderRadius: 6,
  },
  featureContent: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8 },
  featureFree: { color: C.muted, fontSize: 12, flex: 1 },
  featureArrow: { color: C.primary, fontSize: 14, fontWeight: '800' },
  featurePremium: { color: C.success, fontSize: 12, fontWeight: '700', flex: 1, textAlign: 'right' },

  planCard: {
    marginHorizontal: 16, marginBottom: 12, padding: 20,
    backgroundColor: C.surface, borderWidth: 1, borderColor: C.primary, borderRadius: 8,
  },
  planHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  planLabel: { color: C.text, fontSize: 16, fontWeight: '700' },
  saveBadge: { backgroundColor: 'rgba(57, 255, 20, 0.15)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 3 },
  saveText: { color: C.success, fontSize: 9, fontWeight: '800', letterSpacing: 1 },
  planPrice: { flexDirection: 'row', alignItems: 'baseline', gap: 4, marginBottom: 12 },
  priceAmount: { color: C.gold, fontSize: 36, fontWeight: '900' },
  pricePeriod: { color: C.muted, fontSize: 12 },
  planCta: { color: C.primary, fontSize: 13, fontWeight: '800', letterSpacing: 2, textAlign: 'center' },
});
