import React, { useState } from 'react';
import { StyleSheet, Text, View, TextInput, TouchableOpacity } from 'react-native';

export default function ReviewActionScreen() {
  const [explanation, setExplanation] = useState('');
  const [receiptAttached, setReceiptAttached] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Explain Flagged Purchase</Text>
      <Text style={styles.sub}>
        Your parents requested more details for: Epic Games ($49.99)
      </Text>

      {submitted ? (
        <View style={styles.card}>
          <Text style={styles.successText}>✅ Explanation Sent to Parents!</Text>
        </View>
      ) : (
        <View style={styles.card}>
          <Text style={styles.label}>Why was this purchase needed?</Text>
          <TextInput
            style={styles.textArea}
            multiline
            numberOfLines={4}
            placeholder="e.g. It was a season battle pass that includes items for the whole semester..."
            value={explanation}
            onChangeText={setExplanation}
          />

          <TouchableOpacity
            style={[styles.attachBtn, receiptAttached && styles.attachedActive]}
            onPress={() => setReceiptAttached(!receiptAttached)}
          >
            <Text style={styles.attachText}>
              {receiptAttached ? '📎 Receipt Photo Attached (receipt.jpg)' : '📷 Upload Receipt Photo'}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.submitBtn} onPress={() => setSubmitted(true)}>
            <Text style={styles.submitText}>Submit for Parent Review</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc', padding: 16 },
  title: { fontSize: 20, fontWeight: '800', color: '#003087', marginBottom: 4 },
  sub: { fontSize: 13, color: '#64748b', marginBottom: 20 },
  card: { backgroundColor: '#fff', padding: 16, borderRadius: 12, borderWidth: 1, borderColor: '#e2e8f0' },
  label: { fontSize: 13, fontWeight: '600', color: '#334155', marginBottom: 8 },
  textArea: { borderWidth: 1, borderColor: '#cbd5e1', borderRadius: 8, padding: 10, textAlignVertical: 'top', marginBottom: 16 },
  attachBtn: { backgroundColor: '#f1f5f9', padding: 12, borderRadius: 8, alignItems: 'center', marginBottom: 16 },
  attachedActive: { backgroundColor: '#dcfce7', borderWidth: 1, borderColor: '#86efac' },
  attachText: { fontWeight: '600', color: '#334155', fontSize: 13 },
  submitBtn: { backgroundColor: '#0070ba', padding: 14, borderRadius: 8, alignItems: 'center' },
  submitText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  successText: { fontSize: 16, fontWeight: '700', color: '#16a34a', textAlign: 'center' },
});
