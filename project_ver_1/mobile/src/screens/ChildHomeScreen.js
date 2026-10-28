import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

export default function ChildHomeScreen({ transactions = [], budgets = [] }) {
  const totalAllocation = budgets.reduce((sum, item) => sum + Number(item.allocated_amount || 0), 0);
  const totalSpent = budgets.reduce((sum, item) => sum + Number(item.spent_amount || 0), 0);
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={styles.eyebrow}>YOUR FAMILY WALLET</Text>
      <Text style={styles.title}>Your allowance 👋</Text>
      <View style={styles.balanceCard}>
        <Text style={styles.balanceLabel}>Available this month</Text>
        <Text style={styles.balance}>${Math.max(0, totalAllocation - totalSpent).toFixed(2)}</Text>
        <Text style={styles.caption}>remaining in tracked envelopes · USD</Text>
      </View>
      <View style={styles.sectionHeader}><Text style={styles.heading}>Your budgets</Text><Text style={styles.link}>October</Text></View>
      {budgets.map((item) => { const spent = Number(item.spent_amount || 0); const total = Number(item.allocated_amount || 0); return <View key={String(item.id)} style={styles.envelope}><View style={styles.row}><Text style={styles.name}>{item.category_name}</Text><Text style={styles.amount}>${spent.toFixed(2)} / ${total.toFixed(2)}</Text></View><View style={styles.track}><View style={[styles.fill, { width: `${total ? Math.min(100, spent / total * 100) : 0}%` }]} /></View></View>; })}
      {!budgets.length && <Text style={styles.empty}>No budgets have been created for this account.</Text>}
      <View style={styles.sectionHeader}><Text style={styles.heading}>Recent activity</Text></View>
      {transactions.length ? transactions.slice(0, 5).map((transaction) => (
        <View key={String(transaction.id)} style={styles.transaction}>
          <View style={styles.icon}><Text>🧾</Text></View>
          <View style={{ flex: 1 }}><Text style={styles.name}>{transaction.merchant_name}</Text><Text style={styles.caption}>{transaction.category || 'Uncategorized'} · {transaction.status}</Text></View>
          <Text style={styles.name}>−${Number(transaction.amount).toFixed(2)}</Text>
        </View>
      )) : <Text style={styles.empty}>Sign in to sync your transactions.</Text>}
      <Text style={styles.notice}>Need something? Ask your parent before buying with a purchase request.</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 22, paddingTop: 55, backgroundColor: '#f6f8f6', minHeight: '100%' },
  eyebrow: { color: '#738078', fontSize: 11, letterSpacing: 1.4, fontWeight: '700' },
  title: { color: '#17231e', fontSize: 27, fontWeight: '800', marginTop: 8, marginBottom: 20 },
  balanceCard: { backgroundColor: '#006b52', borderRadius: 22, padding: 23, marginBottom: 24 },
  balanceLabel: { color: '#cde4da', fontSize: 13 }, balance: { color: '#fff', fontSize: 40, fontWeight: '800', marginTop: 8 },
  caption: { color: '#87928c', fontSize: 11, marginTop: 4 }, sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 13, marginTop: 6 },
  heading: { color: '#17231e', fontSize: 17, fontWeight: '800' }, link: { color: '#006b52', fontSize: 12, fontWeight: '700' }, envelope: { backgroundColor: '#fff', borderRadius: 15, padding: 15, marginBottom: 10 },
  row: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 11 }, name: { color: '#26332c', fontSize: 13, fontWeight: '700' }, amount: { color: '#75817b', fontSize: 11 },
  track: { height: 7, backgroundColor: '#eef2ef', borderRadius: 9, overflow: 'hidden' }, fill: { height: '100%', borderRadius: 9 },
  transaction: { flexDirection: 'row', alignItems: 'center', gap: 11, backgroundColor: '#fff', padding: 13, borderBottomWidth: 1, borderBottomColor: '#eef1ee' }, icon: { width: 35, height: 35, alignItems: 'center', justifyContent: 'center', backgroundColor: '#eef4ef', borderRadius: 11 },
  empty: { color: '#87928c', padding: 16, fontSize: 12 }, notice: { marginTop: 20, backgroundColor: '#eaf4ef', padding: 14, color: '#236e57', borderRadius: 13, fontSize: 12, lineHeight: 18 },
});
