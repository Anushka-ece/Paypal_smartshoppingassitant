import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';

export default function ParentHomeScreen({ transactions = [], onReview }) {
  const flagged = transactions.filter((item) => item.is_flagged);
  const totalSpent = transactions.reduce((sum, item) => sum + Number(item.amount || 0), 0);
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={styles.eyebrow}>PENNYPILOT FAMILY</Text>
      <Text style={styles.title}>Family overview</Text>
      <View style={styles.cards}>
        <View style={styles.card}><Text style={styles.label}>Allowance</Text><Text style={styles.value}>—</Text><Text style={styles.caption}>Not available from the sync service yet</Text></View>
        <View style={styles.card}><Text style={styles.label}>Tracked spend</Text><Text style={styles.value}>${totalSpent.toFixed(2)}</Text><Text style={styles.caption}>{transactions.length} transaction(s) in current sync</Text></View>
      </View>
      <View style={styles.section}><Text style={styles.heading}>Needs your attention</Text><Text style={styles.caption}>{flagged.length} flagged transactions</Text></View>
      {flagged.length ? flagged.map((item) => (
        <View key={String(item.id)} style={styles.alert}>
          <View style={styles.alertIcon}><Text>⚑</Text></View>
          <View style={{ flex: 1 }}><Text style={styles.name}>{item.merchant_name}</Text><Text style={styles.caption}>${Number(item.amount).toFixed(2)} · {item.risk_level || 'Review'} risk</Text></View>
          <TouchableOpacity style={styles.button} onPress={() => onReview?.(item)}><Text style={styles.buttonText}>Review</Text></TouchableOpacity>
        </View>
      )) : <View style={styles.empty}><Text style={styles.emptyText}>You're all caught up. New alerts will appear here.</Text></View>}
      <View style={styles.section}><Text style={styles.heading}>Latest activity</Text></View>
      {transactions.slice(0, 6).map((item) => <View key={String(item.id)} style={styles.transaction}><View style={{ flex: 1 }}><Text style={styles.name}>{item.merchant_name}</Text><Text style={styles.caption}>{item.category || 'Uncategorized'} · {item.status}</Text></View><Text style={styles.name}>−${Number(item.amount).toFixed(2)}</Text></View>)}
      <Text style={styles.disclaimer}>This companion does not block or reverse PayPal purchases. Review and take any payment action in PayPal.</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 21, paddingTop: 55, backgroundColor: '#f6f8f6', minHeight: '100%' }, eyebrow: { color: '#75817b', fontSize: 11, letterSpacing: 1.4, fontWeight: '700' },
  title: { color: '#17231e', fontSize: 26, fontWeight: '800', marginTop: 8, marginBottom: 19 }, cards: { flexDirection: 'row', gap: 10, marginBottom: 24 }, card: { flex: 1, backgroundColor: '#fff', borderRadius: 16, padding: 15 },
  label: { color: '#75817b', fontSize: 11 }, value: { color: '#17231e', fontSize: 22, fontWeight: '800', marginTop: 10 }, caption: { color: '#75817b', fontSize: 11, marginTop: 5 },
  section: { marginBottom: 11, marginTop: 5 }, heading: { color: '#17231e', fontSize: 17, fontWeight: '800' }, alert: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#fff', padding: 13, borderRadius: 14, marginBottom: 9 },
  alertIcon: { width: 35, height: 35, borderRadius: 11, alignItems: 'center', justifyContent: 'center', backgroundColor: '#fff1da' }, name: { color: '#26332c', fontSize: 13, fontWeight: '700' }, button: { backgroundColor: '#eaf4ef', borderRadius: 9, paddingVertical: 8, paddingHorizontal: 11 }, buttonText: { color: '#006b52', fontSize: 11, fontWeight: '700' },
  empty: { backgroundColor: '#fff', padding: 18, borderRadius: 14 }, emptyText: { color: '#75817b', textAlign: 'center', fontSize: 12 }, transaction: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 13, borderBottomWidth: 1, borderBottomColor: '#e8ede9' },
  disclaimer: { marginTop: 20, color: '#8a6a39', backgroundColor: '#fff6e8', padding: 13, borderRadius: 12, fontSize: 11, lineHeight: 17 },
});
