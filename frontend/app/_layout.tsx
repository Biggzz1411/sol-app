import { Tabs } from 'expo-router';
import { View, StyleSheet } from 'react-native';
import { Crosshair, Radar, Briefcase, Settings, Terminal } from 'lucide-react-native';

const COLORS = {
  bg: '#030206',
  surface: '#0D0814',
  border: '#321B4D',
  primary: '#9D4CDD',
  success: '#39FF14',
  text: '#F4F0FF',
  muted: '#5C4A7A',
};

export default function TabLayout() {
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
