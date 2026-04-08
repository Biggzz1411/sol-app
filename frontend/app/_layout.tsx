import React, { useState } from 'react';
import { Tabs } from 'expo-router';
import { AuthProvider, useAuth } from '../src/AuthContext';
import AuthScreen from '../components/AuthScreen';
import { View, ActivityIndicator, StyleSheet, Text } from 'react-native';
import { Crosshair, Radar, Briefcase, Settings, Terminal, Crown } from 'lucide-react-native';

const COLORS = {
  bg: '#030206',
  surface: '#0D0814',
  border: '#321B4D',
  primary: '#9D4CDD',
  success: '#39FF14',
  gold: '#FFD700',
  text: '#F4F0FF',
  muted: '#5C4A7A',
};

function AppContent() {
  const { user, loading } = useAuth();
  const [guestMode, setGuestMode] = useState(false);

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loadingText}>INITIALIZING...</Text>
      </View>
    );
  }

  if (!user && !guestMode) {
    return <AuthScreen onSkip={() => setGuestMode(true)} />;
  }

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: COLORS.surface,
          borderTopColor: COLORS.border,
          borderTopWidth: 1,
          height: 70,
          paddingBottom: 10,
          paddingTop: 8,
        },
        tabBarActiveTintColor: COLORS.primary,
        tabBarInactiveTintColor: COLORS.muted,
        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: '600',
          letterSpacing: 1,
          textTransform: 'uppercase',
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'HQ',
          tabBarIcon: ({ color, size }) => <Crosshair color={color} size={size} strokeWidth={1.5} />,
        }}
      />
      <Tabs.Screen
        name="scanner"
        options={{
          title: 'Scanner',
          tabBarIcon: ({ color, size }) => <Radar color={color} size={size} strokeWidth={1.5} />,
        }}
      />
      <Tabs.Screen
        name="portfolio"
        options={{
          title: 'Portfolio',
          tabBarIcon: ({ color, size }) => <Briefcase color={color} size={size} strokeWidth={1.5} />,
        }}
      />
      <Tabs.Screen
        name="premium"
        options={{
          title: 'Premium',
          tabBarIcon: ({ color, size }) => <Crown color={color} size={size} strokeWidth={1.5} />,
        }}
      />
      <Tabs.Screen
        name="config"
        options={{
          title: 'Config',
          tabBarIcon: ({ color, size }) => <Settings color={color} size={size} strokeWidth={1.5} />,
        }}
      />
      <Tabs.Screen
        name="logs"
        options={{
          title: 'Logs',
          tabBarIcon: ({ color, size }) => <Terminal color={color} size={size} strokeWidth={1.5} />,
        }}
      />
    </Tabs>
  );
}

export default function TabLayout() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    backgroundColor: COLORS.bg,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 16,
  },
  loadingText: {
    color: COLORS.muted,
    fontSize: 12,
    letterSpacing: 4,
  },
});
