import React from 'react';
import { StyleSheet, Text, View, ScrollView } from 'react-native';

export default function EnvelopesScreen() {
  const envelopes = [
    { id: 1, name: 'Gaming & Apps', spent: 35.0, total: 50.0 },
    { id: 2, name: 'Treats & Snacks', spent: 15.0, total: 40.0 },
    { id: 3, name: 'Books & Supplies', spent: 10.0, total: 30.0 },
  ];

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Your Category Envelopes</Text>
      <Text style={styles.sub}>Track what you have left to spend this month</Text>

      {envelopes.map((env) => {
        const percent = Math.min(100, Math.round((env.spent / env.total) * 100));
        return (
          <View key={env.id} style={styles.card}>
            <View style={styles.row}>
              <Text style={styles.envName}>{env.name}</Text>
              <Text style={styles.envRemaining}>${(env.total - env.spent).toFixed(2)} left</Text>
            </View>
            <View style={styles.progressBarBg}>
              <View style={[styles.progressBarFill, { width: `${percent}%` }]} />
            </View>
            <View style={styles.row}>
              <Text style={styles.meta}>Spent: ${env.spent.toFixed(2)}</Text>
              <Text style={styles.meta}>Limit: ${env.total.toFixed(2)}</Text>
            </View>
          </View>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc', padding: 16 },
  title: { fontSize: 20, fontWeight: '800', color: '#003087', marginBottom: 4 },
  sub: { fontSize: 13, color: '#64748b', marginBottom: 16 },
  card: { backgroundColor: '#fff', padding: 16, borderRadius: 12, marginBottom: 12, borderWidth: 1, borderColor: '#e2e8f0' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  envName: { fontSize: 15, fontWeight: '700', color: '#0f172a' },
  envRemaining: { fontSize: 14, fontWeight: '700', color: '#10b981' },
  progressBarBg: { height: 8, backgroundColor: '#f1f5f9', borderRadius: 4, marginVertical: 10, overflow: 'hidden' },
  progressBarFill: { height: 8, backgroundColor: '#0070ba', borderRadius: 4 },
  meta: { fontSize: 12, color: '#64748b' },
});
