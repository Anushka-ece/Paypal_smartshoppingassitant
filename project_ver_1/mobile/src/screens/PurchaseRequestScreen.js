import React, { useState } from 'react';
import { StyleSheet, Text, View, TextInput, TouchableOpacity, Alert } from 'react-native';

export default function PurchaseRequestScreen() {
  const [itemName, setItemName] = useState('');
  const [storeUrl, setStoreUrl] = useState('');
  const [amount, setAmount] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    if (!itemName || !amount) {
      Alert.alert('Error', 'Please fill in item name and amount.');
      return;
    }
    setSubmitted(true);
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Request a Store Purchase</Text>
      <Text style={styles.sub}>Submit an item link for parents to review and approve</Text>

      {submitted ? (
        <View style={styles.successBox}>
          <Text style={styles.successTitle}>✅ Request Sent!</Text>
          <Text style={styles.successSub}>
            Your parents received an instant approval alert for "{itemName}" (${amount}).
          </Text>
          <TouchableOpacity style={styles.button} onPress={() => setSubmitted(false)}>
            <Text style={styles.buttonText}>Submit Another</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.form}>
          <Text style={styles.label}>Item Name</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g. Science Fair Poster Board"
            value={itemName}
            onChangeText={setItemName}
          />

          <Text style={styles.label}>Store Link / Website URL</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g. https://amazon.com/dp/..."
            value={storeUrl}
            onChangeText={setStoreUrl}
          />

          <Text style={styles.label}>Estimated Cost ($)</Text>
          <TextInput
            style={styles.input}
            placeholder="12.99"
            keyboardType="numeric"
            value={amount}
            onChangeText={setAmount}
          />

          <TouchableOpacity style={styles.button} onPress={handleSubmit}>
            <Text style={styles.buttonText}>Send Request to Parents</Text>
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
  form: { backgroundColor: '#fff', padding: 16, borderRadius: 12, borderWidth: 1, borderColor: '#e2e8f0' },
  label: { fontSize: 13, fontWeight: '600', color: '#334155', marginBottom: 6 },
  input: { borderWidth: 1, borderColor: '#cbd5e1', borderRadius: 8, padding: 10, marginBottom: 16, fontSize: 14 },
  button: { backgroundColor: '#0070ba', padding: 14, borderRadius: 8, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  successBox: { backgroundColor: '#ecfdf5', padding: 20, borderRadius: 12, borderWidth: 1, borderColor: '#a7f3d0', alignItems: 'center' },
  successTitle: { fontSize: 18, fontWeight: '800', color: '#065f46', marginBottom: 8 },
  successSub: { fontSize: 14, color: '#047857', textAlign: 'center', marginBottom: 16 },
});
