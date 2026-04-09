import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Platform, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { useAuth } from '../src/AuthContext';
import { useLocalSearchParams } from 'expo-router';
import { Crown, Check, Zap, Shield, Wallet, Bell, Gauge, Copy, RefreshCw, CreditCard, Users, Share2 } from 'lucide-react-native';
import * as Clipboard from 'expo-clipboard';

const API = process.env.EXPO_PUBLIC_BACKEND_URL;

const C = {
  bg: '#030206', surface: '#0D0814', border: '#321B4D',
  primary: '#9D4CDD', success: '#39FF14', danger: '#FF2A2A',
  warning: '#FFD700', gold: '#FFD700', text: '#F4F0FF',
  textSec: '#A390C2', muted: '#5C4A7A',
};

export default function PremiumScreen() {
  const { user, token, refresh } = useAuth();
  const params = useLocalSearchParams();
  const [plans, setPlans] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [solOrder, setSolOrder] = useState<any>(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<any>(null);
  const [initiating, setInitiating] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [referralData, setReferralData] = useState<any>(null);
  const [copiedRef, setCopiedRef] = useState(false);

  const isPremium = user?.is_premium || user?.subscription?.status === 'active';

  useEffect(() => { fetchPlans(); fetchReferral(); }, []);

  const fetchPlans = async () => {
    try {
      const res = await fetch(`${API}/api/premium/plans`);
      setPlans(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const fetchReferral = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API}/api/referral/code`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) setReferralData(await res.json());
    } catch (e) { console.error(e); }
  };

  const copyReferralCode = async () => {
    if (referralData?.referral_code) {
      await Clipboard.setStringAsync(referralData.referral_code);
      setCopiedRef(true);
      setTimeout(() => setCopiedRef(false), 2000);
    }
  };

  const initiateSolPayment = async (planId: string) => {
    if (!token) return;
    setInitiating(planId);
    setVerifyResult(null);
    try {
      const res = await fetch(`${API}/api/premium/sol/initiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ plan_id: planId }),
      });
      const data = await res.json();
      setSolOrder(data);
    } catch (e) { console.error(e); }
    finally { setInitiating(null); }
  };

  const verifySolPayment = async () => {
    if (!solOrder || !token) return;
    setVerifying(true);
    setVerifyResult(null);
    try {
      const res = await fetch(`${API}/api/premium/sol/verify/${solOrder.order_id}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      setVerifyResult(data);
      if (data.status === 'paid') {
        await refresh();
      }
    } catch (e) { console.error(e); }
    finally { setVerifying(false); }
  };

  const copyAddress = async () => {
    if (solOrder?.wallet_address) {
      await Clipboard.setStringAsync(solOrder.wallet_address);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const copyAmount = async () => {
    if (solOrder?.amount_sol) {
      await Clipboard.setStringAsync(String(solOrder.amount_sol));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleStripeCheckout = async (planId: string) => {
    if (!token) return;
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
          (window as any).location.href = data.url;
        } else {
          const { Linking } = require('react-native');
          await Linking.openURL(data.url);
        }
      }
    } catch (e) { console.error(e); }
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

        {/* Already Premium */}
        {isPremium ? (
          <View style={styles.activeCard}>
            <View style={styles.activeHeader}>
              <Crown color={C.gold} size={24} />
              <Text style={styles.activeTitle}>PREMIUM ACTIVE</Text>
            </View>
            <Text style={styles.activePlan}>
              {user?.subscription?.plan === 'admin' ? 'OWNER' : user?.subscription?.plan?.toUpperCase()} PLAN
            </Text>
            {user?.subscription?.plan === 'admin' ? (
              <Text style={[styles.activeExpiry, { color: C.gold }]}>
                Lifetime Access — No Expiration
              </Text>
            ) : user?.subscription?.expires_at ? (
              <Text style={styles.activeExpiry}>
                Expires: {new Date(user.subscription.expires_at).toLocaleDateString()}
              </Text>
            ) : null}
            {user?.subscription?.payment_method && (
              <Text style={styles.activeMethod}>
                Paid via: {user.subscription.payment_method.toUpperCase()}
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

            {/* SOL Payment Active Order */}
            {solOrder && !verifyResult?.status?.includes('paid') && (
              <View style={styles.orderCard}>
                <Text style={styles.orderTitle}>SEND SOL TO ACTIVATE</Text>

                <Text style={styles.orderLabel}>SEND EXACTLY:</Text>
                <TouchableOpacity testID="copy-amount-btn" style={styles.copyRow} onPress={copyAmount}>
                  <Text style={styles.orderAmount}>{solOrder.amount_sol} SOL</Text>
                  <Copy color={C.muted} size={14} />
                </TouchableOpacity>

                <Text style={styles.orderLabel}>TO THIS WALLET:</Text>
                <TouchableOpacity testID="copy-address-btn" style={styles.copyRow} onPress={copyAddress}>
                  <Text style={styles.orderAddress} numberOfLines={1}>
                    {solOrder.wallet_address}
                  </Text>
                  <Copy color={C.muted} size={14} />
                </TouchableOpacity>

                {copied && <Text style={styles.copiedText}>Copied!</Text>}

                <Text style={styles.orderNote}>
                  Send the EXACT amount from any Solana wallet. The unique amount helps us identify your payment automatically.
                </Text>
                <Text style={styles.orderExpiry}>
                  Expires in 30 minutes
                </Text>

                <TouchableOpacity
                  testID="verify-sol-payment-btn"
                  style={styles.verifyBtn}
                  onPress={verifySolPayment}
                  disabled={verifying}
                >
                  {verifying ? (
                    <ActivityIndicator size="small" color={C.success} />
                  ) : (
                    <>
                      <RefreshCw color={C.success} size={16} />
                      <Text style={styles.verifyBtnText}>VERIFY PAYMENT</Text>
                    </>
                  )}
                </TouchableOpacity>

                {verifyResult && verifyResult.status === 'pending' && (
                  <Text style={styles.pendingText}>
                    Payment not detected yet. Make sure you sent the exact amount and try again.
                  </Text>
                )}
                {verifyResult && verifyResult.status === 'expired' && (
                  <Text style={styles.expiredText}>
                    Payment window expired. Please create a new order below.
                  </Text>
                )}
              </View>
            )}

            {/* Payment Success */}
            {verifyResult?.status === 'paid' && (
              <View style={[styles.orderCard, { borderColor: C.success }]}>
                <View style={styles.successRow}>
                  <Check color={C.success} size={24} />
                  <Text style={styles.successText}>PREMIUM ACTIVATED!</Text>
                </View>
                <Text style={styles.successTx}>
                  TX: {verifyResult.tx_signature?.slice(0, 24)}...
                </Text>
                <Text style={styles.successAmount}>
                  {verifyResult.amount_sol} SOL received
                </Text>
              </View>
            )}

            {/* Plan Cards */}
            {!isPremium && (
              <>
                <Text style={styles.sectionTitle}>CHOOSE YOUR PLAN</Text>
                {plans?.plans && Object.entries(plans.plans).map(([id, plan]: [string, any]) => (
                  <TouchableOpacity
                    key={id}
                    testID={`plan-${id}-btn`}
                    style={styles.planCard}
                    onPress={() => initiateSolPayment(id)}
                    disabled={initiating === id}
                    activeOpacity={0.7}
                  >
                    <View style={styles.planHeader}>
                      <Text style={styles.planLabel}>{plan.label}</Text>
                      {plan.save_pct && (
                        <View style={styles.saveBadge}>
                          <Text style={styles.saveText}>SAVE {plan.save_pct}%</Text>
                        </View>
                      )}
                    </View>
                    <View style={styles.planPricing}>
                      <View style={styles.planSolPrice}>
                        <Text style={styles.solAmount}>{plan.price_sol}</Text>
                        <Text style={styles.solUnit}> SOL</Text>
                      </View>
                      <Text style={styles.usdEquiv}>~${plan.price_usd} USD</Text>
                    </View>
                    <Text style={styles.planDuration}>{plan.duration_days} days access</Text>
                    {initiating === id ? (
                      <ActivityIndicator size="small" color={C.primary} style={{ marginTop: 8 }} />
                    ) : (
                      <View style={styles.planCtaRow}>
                        <Wallet color={C.primary} size={14} />
                        <Text style={styles.planCta}>PAY WITH SOL</Text>
                      </View>
                    )}
                  </TouchableOpacity>
                ))}

                {/* Stripe Option */}
                <TouchableOpacity
                  testID="stripe-pay-btn"
                  style={styles.stripeBanner}
                  onPress={() => {
                    if (plans?.plans?.monthly) {
                      handleStripeCheckout('monthly');
                    }
                  }}
                >
                  <CreditCard color={C.textSec} size={18} />
                  <View>
                    <Text style={styles.stripeTitle}>PAY WITH CARD</Text>
                    <Text style={styles.stripeSubtext}>Via Stripe — $29/mo or $69/quarter</Text>
                  </View>
                </TouchableOpacity>
              </>
            )}
          </>
        )}

        {/* Referral Program */}
        {token && referralData && (
          <>
            <Text style={styles.sectionTitle}>REFERRAL PROGRAM</Text>
            <View style={styles.referralCard}>
              <View style={styles.referralHeader}>
                <Users color={C.primary} size={20} />
                <Text style={styles.referralTitle}>SHARE & EARN</Text>
              </View>
              <Text style={styles.referralDesc}>
                You get 7 days free premium for each referral. New users get 3 days free when they use your code.
              </Text>
              <Text style={styles.referralLabel}>YOUR CODE</Text>
              <TouchableOpacity testID="copy-referral-btn" style={styles.referralCodeRow} onPress={copyReferralCode}>
                <Text style={styles.referralCode}>{referralData.referral_code}</Text>
                <Copy color={C.muted} size={14} />
              </TouchableOpacity>
              {copiedRef && <Text style={styles.copiedRefText}>Copied!</Text>}
              <View style={styles.referralStats}>
                <View style={styles.referralStat}>
                  <Text style={styles.referralStatValue}>{referralData.referral_count || 0}</Text>
                  <Text style={styles.referralStatLabel}>REFERRALS</Text>
                </View>
                <View style={styles.referralStat}>
                  <Text style={styles.referralStatValue}>{(referralData.referral_count || 0) * 7}d</Text>
                  <Text style={styles.referralStatLabel}>EARNED</Text>
                </View>
              </View>
            </View>
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

  activeCard: {
    marginHorizontal: 16, marginBottom: 20, padding: 24,
    backgroundColor: C.surface, borderWidth: 2, borderColor: C.gold, borderRadius: 8,
  },
  activeHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  activeTitle: { color: C.gold, fontSize: 18, fontWeight: '800', letterSpacing: 2 },
  activePlan: { color: C.text, fontSize: 14, fontWeight: '600' },
  activeExpiry: { color: C.muted, fontSize: 12, marginTop: 4 },
  activeMethod: { color: C.textSec, fontSize: 11, marginTop: 2 },

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

  // SOL Payment Order
  orderCard: {
    marginHorizontal: 16, marginBottom: 16, padding: 20,
    backgroundColor: C.surface, borderWidth: 2, borderColor: C.primary, borderRadius: 8,
  },
  orderTitle: { color: C.primary, fontSize: 14, fontWeight: '800', letterSpacing: 2, marginBottom: 16 },
  orderLabel: { color: C.muted, fontSize: 9, fontWeight: '700', letterSpacing: 3, marginBottom: 6, marginTop: 12 },
  copyRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#1A1025', padding: 12, borderRadius: 4, borderWidth: 1, borderColor: C.border,
  },
  orderAmount: {
    color: C.gold, fontSize: 24, fontWeight: '900',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  orderAddress: {
    color: C.textSec, fontSize: 11, flex: 1, marginRight: 8,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  copiedText: { color: C.success, fontSize: 11, marginTop: 4, textAlign: 'center' },
  orderNote: { color: C.muted, fontSize: 11, marginTop: 12, lineHeight: 16 },
  orderExpiry: { color: C.warning, fontSize: 10, fontWeight: '700', marginTop: 8 },
  verifyBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    marginTop: 16, paddingVertical: 14, borderWidth: 1,
    borderColor: C.success, borderRadius: 6, backgroundColor: 'rgba(57, 255, 20, 0.08)',
  },
  verifyBtnText: { color: C.success, fontSize: 13, fontWeight: '800', letterSpacing: 2 },
  pendingText: { color: C.warning, fontSize: 11, marginTop: 10, textAlign: 'center' },
  expiredText: { color: C.danger, fontSize: 11, marginTop: 10, textAlign: 'center' },

  // Success
  successRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  successText: { color: C.success, fontSize: 18, fontWeight: '900', letterSpacing: 2 },
  successTx: {
    color: C.textSec, fontSize: 10, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  successAmount: { color: C.gold, fontSize: 14, fontWeight: '700', marginTop: 4 },

  // Plan Cards
  planCard: {
    marginHorizontal: 16, marginBottom: 12, padding: 20,
    backgroundColor: C.surface, borderWidth: 1, borderColor: C.primary, borderRadius: 8,
  },
  planHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  planLabel: { color: C.text, fontSize: 16, fontWeight: '700' },
  saveBadge: { backgroundColor: 'rgba(57, 255, 20, 0.15)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 3 },
  saveText: { color: C.success, fontSize: 9, fontWeight: '800', letterSpacing: 1 },
  planPricing: { flexDirection: 'row', alignItems: 'baseline', gap: 12, marginBottom: 4 },
  planSolPrice: { flexDirection: 'row', alignItems: 'baseline' },
  solAmount: { color: C.gold, fontSize: 36, fontWeight: '900' },
  solUnit: { color: C.gold, fontSize: 16, fontWeight: '700' },
  usdEquiv: { color: C.muted, fontSize: 12 },
  planDuration: { color: C.textSec, fontSize: 12, marginBottom: 4 },
  planCtaRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 8 },
  planCta: { color: C.primary, fontSize: 13, fontWeight: '800', letterSpacing: 2 },

  // Stripe Banner
  stripeBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    marginHorizontal: 16, marginTop: 8, padding: 14,
    backgroundColor: C.surface, borderWidth: 1, borderColor: '#635BFF',
    borderRadius: 6,
  },
  stripeTitle: { color: '#635BFF', fontSize: 12, fontWeight: '700', letterSpacing: 1 },
  stripeSubtext: { color: C.muted, fontSize: 10 },

  // Referral
  referralCard: {
    marginHorizontal: 16, marginBottom: 16, padding: 20,
    backgroundColor: C.surface, borderWidth: 1, borderColor: C.primary, borderRadius: 8,
  },
  referralHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  referralTitle: { color: C.primary, fontSize: 16, fontWeight: '800', letterSpacing: 2 },
  referralDesc: { color: C.textSec, fontSize: 12, lineHeight: 18, marginBottom: 16 },
  referralLabel: { color: C.muted, fontSize: 9, fontWeight: '700', letterSpacing: 3, marginBottom: 6 },
  referralCodeRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#1A1025', padding: 14, borderRadius: 4, borderWidth: 1, borderColor: C.border,
  },
  referralCode: {
    color: C.gold, fontSize: 20, fontWeight: '900', letterSpacing: 4,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  copiedRefText: { color: C.success, fontSize: 11, marginTop: 4, textAlign: 'center' },
  referralStats: { flexDirection: 'row', gap: 16, marginTop: 16 },
  referralStat: { flex: 1, alignItems: 'center', padding: 12, backgroundColor: '#1A1025', borderRadius: 4 },
  referralStatValue: { color: C.text, fontSize: 24, fontWeight: '900' },
  referralStatLabel: { color: C.muted, fontSize: 8, fontWeight: '700', letterSpacing: 2, marginTop: 4 },
});
