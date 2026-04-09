import React, { useState } from 'react';
import {
  View, Text, StyleSheet, TextInput, TouchableOpacity,
  KeyboardAvoidingView, Platform, ActivityIndicator, ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { useAuth } from '../src/AuthContext';
import { Zap, Mail, Lock, User } from 'lucide-react-native';

const C = {
  bg: '#030206', surface: '#0D0814', border: '#321B4D',
  primary: '#9D4CDD', success: '#39FF14', danger: '#FF2A2A',
  text: '#F4F0FF', textSec: '#A390C2', muted: '#5C4A7A',
};

export default function AuthScreen({ onSkip }: { onSkip?: () => void }) {
  const { login, register } = useAuth();
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [referralCode, setReferralCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setError('');
    if (!email.trim() || !password.trim()) {
      setError('Email and password required');
      return;
    }
    setLoading(true);
    try {
      const result = isLogin
        ? await login(email.trim(), password)
        : await register(email.trim(), password, name.trim(), referralCode.trim());
      if (!result.success) {
        setError(result.error || 'Something went wrong');
      }
    } catch (e: any) {
      setError(e.message || 'Error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {/* Logo Area */}
          <View style={styles.logoSection}>
            <View style={styles.logoRing}>
              <Zap color={C.success} size={48} strokeWidth={2} />
            </View>
            <Text style={styles.appTitle}>SOLANA SNIPER</Text>
            <Text style={styles.appSubtitle}>INTERSTELLAR TRADING SYSTEM</Text>
          </View>

          {/* Toggle */}
          <View style={styles.toggleRow}>
            <TouchableOpacity
              testID="auth-login-tab"
              style={[styles.toggleBtn, isLogin && styles.toggleActive]}
              onPress={() => { setIsLogin(true); setError(''); }}
            >
              <Text style={[styles.toggleText, isLogin && styles.toggleTextActive]}>LOGIN</Text>
            </TouchableOpacity>
            <TouchableOpacity
              testID="auth-register-tab"
              style={[styles.toggleBtn, !isLogin && styles.toggleActive]}
              onPress={() => { setIsLogin(false); setError(''); }}
            >
              <Text style={[styles.toggleText, !isLogin && styles.toggleTextActive]}>REGISTER</Text>
            </TouchableOpacity>
          </View>

          {/* Form */}
          <View style={styles.form}>
            {!isLogin && (
              <View style={styles.inputRow}>
                <User color={C.muted} size={18} />
                <TextInput
                  testID="auth-name-input"
                  style={styles.input}
                  placeholder="Name"
                  placeholderTextColor={C.muted}
                  value={name}
                  onChangeText={setName}
                  autoCapitalize="words"
                />
              </View>
            )}
            <View style={styles.inputRow}>
              <Mail color={C.muted} size={18} />
              <TextInput
                testID="auth-email-input"
                style={styles.input}
                placeholder="Email"
                placeholderTextColor={C.muted}
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                keyboardType="email-address"
                autoCorrect={false}
              />
            </View>
            <View style={styles.inputRow}>
              <Lock color={C.muted} size={18} />
              <TextInput
                testID="auth-password-input"
                style={styles.input}
                placeholder="Password"
                placeholderTextColor={C.muted}
                value={password}
                onChangeText={setPassword}
                secureTextEntry
              />
            </View>

            {!isLogin && (
              <View style={styles.inputRow}>
                <Zap color={C.muted} size={18} />
                <TextInput
                  testID="auth-referral-input"
                  style={styles.input}
                  placeholder="Referral code (optional)"
                  placeholderTextColor={C.muted}
                  value={referralCode}
                  onChangeText={setReferralCode}
                  autoCapitalize="characters"
                  autoCorrect={false}
                />
              </View>
            )}

            {error ? <Text style={styles.errorText}>{error}</Text> : null}

            <TouchableOpacity
              testID="auth-submit-btn"
              style={styles.submitBtn}
              onPress={handleSubmit}
              disabled={loading}
              activeOpacity={0.7}
            >
              {loading ? (
                <ActivityIndicator size="small" color={C.bg} />
              ) : (
                <Text style={styles.submitBtnText}>
                  {isLogin ? 'ENGAGE' : 'CREATE ACCOUNT'}
                </Text>
              )}
            </TouchableOpacity>
          </View>

          {/* Skip */}
          {onSkip && (
            <TouchableOpacity testID="auth-skip-btn" style={styles.skipBtn} onPress={onSkip}>
              <Text style={styles.skipText}>EXPLORE IN GUEST MODE</Text>
            </TouchableOpacity>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bg },
  scrollContent: { flexGrow: 1, justifyContent: 'center', paddingHorizontal: 24, paddingVertical: 40 },
  logoSection: { alignItems: 'center', marginBottom: 48 },
  logoRing: {
    width: 100, height: 100, borderRadius: 50, borderWidth: 2, borderColor: C.success,
    backgroundColor: 'rgba(57, 255, 20, 0.06)', justifyContent: 'center', alignItems: 'center',
    marginBottom: 20,
  },
  appTitle: { color: C.text, fontSize: 32, fontWeight: '900', letterSpacing: 4 },
  appSubtitle: { color: C.muted, fontSize: 10, letterSpacing: 6, marginTop: 6 },

  toggleRow: { flexDirection: 'row', gap: 12, marginBottom: 24 },
  toggleBtn: {
    flex: 1, paddingVertical: 12, alignItems: 'center',
    borderWidth: 1, borderColor: C.border, borderRadius: 4, backgroundColor: C.surface,
  },
  toggleActive: { borderColor: C.primary, backgroundColor: 'rgba(157, 76, 221, 0.15)' },
  toggleText: { color: C.muted, fontSize: 13, fontWeight: '700', letterSpacing: 2 },
  toggleTextActive: { color: C.primary },

  form: { gap: 14 },
  inputRow: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: C.surface, borderWidth: 1, borderColor: C.border,
    borderRadius: 6, paddingHorizontal: 16, height: 52,
  },
  input: { flex: 1, color: C.text, fontSize: 15 },
  errorText: { color: C.danger, fontSize: 12, textAlign: 'center' },

  submitBtn: {
    marginTop: 8, paddingVertical: 16, alignItems: 'center',
    backgroundColor: C.primary, borderRadius: 6,
  },
  submitBtnText: { color: C.bg, fontSize: 15, fontWeight: '800', letterSpacing: 2 },

  skipBtn: { marginTop: 32, alignItems: 'center', paddingVertical: 12 },
  skipText: { color: C.muted, fontSize: 11, letterSpacing: 3 },
});
