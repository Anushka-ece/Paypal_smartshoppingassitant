import React from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity } from 'react-native';

export default function HomeScreen({ role, onSwitchRole, onTriggerAlert }) {
  const isParent = role === 'PARENT';

  return (
    <ScrollView style={styles.container}>
      {/* Top Bar */}
      <View style={styles.topBar}>
        <Text style={styles.brand}>PayPal Family</Text>
        <TouchableOpacity style={styles.roleTag} onPress={onSwitchRole}>
          <Text style={styles.roleText}>Mode: {role} (Tap to Switch)</Text>
        </TouchableOpacity>
      </View>

      {/* Balance Card */}
      <View style={styles.balanceCard}>
        <Text style={styles.balanceTitle}>
          {isParent ? 'Total Family Available Balance' : 'Your Pocket Money Balance'}
        </Text>
        <Text style={styles.balanceAmount}>{isParent ? '$1,250.00' : '$45.00'}</Text>
        <Text style={styles.balanceSub}>
          {isParent ? 'PayPal Linked Master Wallet' : 'Weekly Allowance: $15.00 (Active)'}
        </Text>
      </View>

      {/* Quick Actions */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Quick Actions</Text>
      </View>

      {isParent ? (
        <View style={styles.actionsRow}>
          <TouchableOpacity
            style={[styles.actionBtn, { backgroundColor: '#fee2e2' }]}
            onPress={onTriggerAlert}
          >
            <Text style={[styles.actionBtnText, { color: '#991b1b' }]}>🚨 Test Push Alert</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.actionsRow}>
          <View style={[styles.actionBtn, { backgroundColor: '#e0f2fe' }]}>
            <Text style={[styles.actionBtnText, { color: '#0369a1' }]}>🛍️ Pre-Purchase Link</Text>
          </View>
        </View>
      )}

      {/* Recent Activity */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Recent Transactions</Text>
      </View>

      <View style={styles.transactionCard}>
        <View style={styles.txRow}>
          <Text style={styles.txMerchant}>Steam Games</Text>
          <Text style={styles.txAmount}>-$19.99</Text>
        </View>
        <Text style={styles.txMeta}>Gaming • Yesterday</Text>
      </View>

      <View style={styles.transactionCard}>
        <View style={styles.txRow}>
          <Text style={styles.txMerchant}>Starbucks Coffee</Text>
          <Text style={styles.txAmount}>-$5.50</Text>
        </View>
        <Text style={styles.txMeta}>Food & Dining • Oct 29</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
    padding: 16,
  },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  brand: {
    fontSize: 20,
    fontWeight: '800',
    color: '#003087',
  },
  roleTag: {
    backgroundColor: '#e2e8f0',
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 12,
  },
  roleText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#334155',
  },
  balanceCard: {
    backgroundColor: '#003087',
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
  },
  balanceTitle: {
    color: '#93c5fd',
    fontSize: 13,
    fontWeight: '600',
  },
  balanceAmount: {
    color: '#ffffff',
    fontSize: 32,
    fontWeight: '800',
    marginVertical: 6,
  },
  balanceSub: {
    color: '#bfdbfe',
    fontSize: 12,
  },
  sectionHeader: {
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0f172a',
  },
  actionsRow: {
    flexDirection: 'row',
    marginBottom: 20,
  },
  actionBtn: {
    flex: 1,
    padding: 12,
    borderRadius: 10,
    alignItems: 'center',
  },
  actionBtnText: {
    fontWeight: '700',
    fontSize: 13,
  },
  transactionCard: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  txRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  txMerchant: {
    fontSize: 15,
    fontWeight: '600',
    color: '#0f172a',
  },
  txAmount: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0f172a',
  },
  txMeta: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 4,
  },
});
