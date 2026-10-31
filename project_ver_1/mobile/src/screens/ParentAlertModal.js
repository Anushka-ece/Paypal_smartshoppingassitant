import React from 'react';
import { StyleSheet, Text, View, Modal, TouchableOpacity } from 'react-native';

export default function ParentAlertModal({ visible, alertData, onClose, onAction }) {
  if (!alertData) return null;

  return (
    <Modal visible={visible} transparent animationType="slide">
      <View style={styles.overlay}>
        <View style={styles.modalCard}>
          <View style={styles.headerRow}>
            <Text style={styles.alertBadge}>🚨 HIGH RISK ALERT</Text>
            <Text style={styles.amount}>${alertData.amount?.toFixed(2)}</Text>
          </View>

          <Text style={styles.merchant}>{alertData.merchant}</Text>
          <Text style={styles.childText}>Spender: {alertData.child}</Text>

          <View style={styles.reasonBox}>
            <Text style={styles.reasonText}>{alertData.summary || alertData.flagReason}</Text>
          </View>

          <View style={styles.buttonRow}>
            <TouchableOpacity
              style={[styles.button, styles.approveBtn]}
              onPress={() => onAction('APPROVE', alertData)}
            >
              <Text style={styles.btnText}>Approve</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.button, styles.reviewBtn]}
              onPress={() => onAction('REQUEST_REVIEW', alertData)}
            >
              <Text style={styles.btnText}>Request Info</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.button, styles.disputeBtn]}
              onPress={() => onAction('FREEZE_DISPUTE', alertData)}
            >
              <Text style={styles.btnText}>Freeze/Dispute</Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity style={styles.dismissBtn} onPress={onClose}>
            <Text style={styles.dismissText}>Dismiss</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    padding: 20,
  },
  modalCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 20,
    elevation: 5,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  alertBadge: {
    backgroundColor: '#fee2e2',
    color: '#b91c1c',
    fontWeight: 'bold',
    fontSize: 12,
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  amount: {
    fontSize: 22,
    fontWeight: '800',
    color: '#003087',
  },
  merchant: {
    fontSize: 18,
    fontWeight: '700',
    color: '#0f172a',
  },
  childText: {
    fontSize: 14,
    color: '#64748b',
    marginTop: 2,
    marginBottom: 12,
  },
  reasonBox: {
    backgroundColor: '#fff7ed',
    borderLeftWidth: 4,
    borderLeftColor: '#f97316',
    padding: 10,
    borderRadius: 6,
    marginBottom: 16,
  },
  reasonText: {
    color: '#9a3412',
    fontSize: 13,
    lineHeight: 18,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'space-between',
  },
  button: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
  approveBtn: {
    backgroundColor: '#10b981',
  },
  reviewBtn: {
    backgroundColor: '#f59e0b',
  },
  disputeBtn: {
    backgroundColor: '#ef4444',
  },
  btnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 12,
  },
  dismissBtn: {
    marginTop: 12,
    alignItems: 'center',
  },
  dismissText: {
    color: '#64748b',
    fontSize: 13,
  },
});
