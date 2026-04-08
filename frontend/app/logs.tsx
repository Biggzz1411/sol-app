import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  RefreshControl, ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { Terminal, Trash2 } from 'lucide-react-native';

const API = process.env.EXPO_PUBLIC_BACKEND_URL;

const C = {
  bg: '#030206',
  surface: '#0D0814',
  border: '#321B4D',
  primary: '#9D4CDD',
  success: '#39FF14',
  danger: '#FF2A2A',
  warning: '#FFD700',
  text: '#F4F0FF',
  textSec: '#A390C2',
  muted: '#5C4A7A',
};

const levelColors: Record<string, string> = {
  info: '#A390C2',
  success: '#39FF14',
  warn: '#FFD700',
  error: '#FF2A2A',
  snipe: '#9D4CDD',
  sell: '#FF8C00',
  debug: '#5C4A7A',
};

const levelIcons: Record<string, string> = {
  info: 'INF',
  success: 'OK!',
  warn: 'WRN',
  error: 'ERR',
  snipe: 'SNP',
  sell: 'SLL',
  debug: 'DBG',
};

export default function LogsScreen() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/logs?limit=200`);
      const data = await res.json();
      setLogs(data.reverse());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  useEffect(() => {
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, [fetchLogs]);

  const clearLogs = async () => {
    try {
      await fetch(`${API}/api/logs`, { method: 'DELETE' });
      setLogs([]);
    } catch (e) {
      console.error(e);
    }
  };

  const formatTime = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString('en-US', { hour12: false });
    } catch {
      return '??:??:??';
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />

      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Terminal color={C.primary} size={22} />
          <Text style={styles.headerTitle}>ACTIVITY LOG</Text>
        </View>
        <TouchableOpacity testID="clear-logs-btn" style={styles.clearBtn} onPress={clearLogs}>
          <Trash2 color={C.danger} size={16} />
        </TouchableOpacity>
      </View>

      <View style={styles.terminalContainer}>
        {loading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={C.primary} />
          </View>
        ) : logs.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>{'>'} AWAITING LOG DATA...</Text>
            <Text style={styles.cursorBlink}>_</Text>
          </View>
        ) : (
          <FlatList
            ref={flatListRef}
            data={logs}
            keyExtractor={(item) => item.id}
            onContentSizeChange={() => {
              if (flatListRef.current && logs.length > 0) {
                flatListRef.current.scrollToEnd({ animated: false });
              }
            }}
            refreshControl={
              <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchLogs(); }} tintColor={C.primary} />
            }
            renderItem={({ item }) => {
              const color = levelColors[item.level] || C.muted;
              const icon = levelIcons[item.level] || 'LOG';

              return (
                <View style={styles.logRow}>
                  <Text style={[styles.logTime, { color: C.muted }]}>
                    {formatTime(item.timestamp)}
                  </Text>
                  <Text style={[styles.logLevel, { color }]}>
                    [{icon}]
                  </Text>
                  <Text style={[styles.logMessage, { color }]} numberOfLines={3}>
                    {item.message}
                  </Text>
                </View>
              );
            }}
            contentContainerStyle={{ paddingBottom: 16, paddingTop: 8 }}
          />
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000000' },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 20, paddingTop: 12, paddingBottom: 12,
    backgroundColor: '#030206', borderBottomWidth: 1, borderBottomColor: '#321B4D',
  },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  headerTitle: { color: '#F4F0FF', fontSize: 22, fontWeight: '800', letterSpacing: 2 },
  clearBtn: {
    width: 40, height: 40, borderRadius: 4, borderWidth: 1, borderColor: '#FF2A2A',
    backgroundColor: 'rgba(255,42,42,0.1)', justifyContent: 'center', alignItems: 'center',
  },

  terminalContainer: {
    flex: 1, backgroundColor: '#000000',
    borderLeftWidth: 2, borderLeftColor: '#9D4CDD',
  },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyContainer: {
    flex: 1, justifyContent: 'center', alignItems: 'center',
    flexDirection: 'row', gap: 4,
  },
  emptyText: {
    color: '#39FF14', fontSize: 14,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  cursorBlink: {
    color: '#39FF14', fontSize: 14,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },

  logRow: {
    flexDirection: 'row', paddingHorizontal: 12, paddingVertical: 3, gap: 8,
    alignItems: 'flex-start',
  },
  logTime: {
    fontSize: 10, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    width: 64,
  },
  logLevel: {
    fontSize: 10, fontWeight: '800',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    width: 36,
  },
  logMessage: {
    fontSize: 11, flex: 1,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
});
