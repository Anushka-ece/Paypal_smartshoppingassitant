import React, { useState } from 'react';
import { StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';

export default function PurchaseRequestScreen({ onSubmit, onCancel }) {
  const [merchant, setMerchant] = useState('');
  const [itemUrl, setItemUrl] = useState('');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');

  function submit() {
    const parsedAmount = Number(amount);
    if (!merchant.trim() || !Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      setError('Enter the store and a valid positive amount.');
      return;
    }
    if (itemUrl && !/^https:\/\//i.test(itemUrl)) {
      setError('Use a secure https:// link, or leave the link blank.');
      return;
    }
    setError('');
    onSubmit?.({ merchant: merchant.trim(), item_url: itemUrl.trim(), amount: parsedAmount, currency: 'USD', note: note.trim() });
  }

  return (
    <View style={styles.page}>
      <Text style={styles.eyebrow}>ASK BEFORE YOU BUY</Text>
      <Text style={styles.title}>Purchase request</Text>
      <Text style={styles.subtitle}>Send the details to your parent for approval. Submitting a request does not pay the store.</Text>
      <TextInput value={merchant} onChangeText={setMerchant} placeholder="Store or merchant" style={styles.input} />
      <TextInput value={itemUrl} onChangeText={setItemUrl} placeholder="Product link (optional)" autoCapitalize="none" keyboardType="url" style={styles.input} />
      <TextInput value={amount} onChangeText={setAmount} placeholder="Amount in USD" keyboardType="decimal-pad" style={styles.input} />
      <TextInput value={note} onChangeText={setNote} placeholder="Why do you want it? (optional)" multiline style={[styles.input, styles.multiline]} />
      {!!error && <Text style={styles.error}>{error}</Text>}
      <TouchableOpacity style={styles.button} onPress={submit}><Text style={styles.buttonText}>Send request</Text></TouchableOpacity>
      <TouchableOpacity style={styles.cancel} onPress={onCancel}><Text style={styles.cancelText}>Cancel</Text></TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#f6f8f6', padding: 23, paddingTop: 55 }, eyebrow: { color: '#75817b', fontSize: 11, letterSpacing: 1.3, fontWeight: '700' },
  title: { color: '#17231e', fontSize: 27, fontWeight: '800', marginTop: 8 }, subtitle: { color: '#75817b', fontSize: 13, lineHeight: 19, marginVertical: 13 },
  input: { padding: 14, backgroundColor: '#fff', borderColor: '#e7ece8', borderWidth: 1, borderRadius: 12, marginBottom: 10, color: '#17231e' }, multiline: { minHeight: 86, textAlignVertical: 'top' },
  button: { backgroundColor: '#006b52', padding: 15, borderRadius: 12, alignItems: 'center', marginTop: 5 }, buttonText: { color: '#fff', fontWeight: '700' }, cancel: { padding: 13, alignItems: 'center' }, cancelText: { color: '#75817b', fontWeight: '600' }, error: { color: '#b64040', marginBottom: 8, fontSize: 12 },
});
