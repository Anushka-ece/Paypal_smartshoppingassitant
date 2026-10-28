import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { apiRequest } from '../services/api';

export default function BudgetsScreen({ role, token }) {
  const [budgets, setBudgets] = useState([]);
  const [category, setCategory] = useState('Free spend');
  const [amount, setAmount] = useState('50.00');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function load() {
    setBusy(true);
    try { setBudgets(await apiRequest('/allowances/', { token })); }
    catch (error) { setMessage(error.message || 'Unable to load budgets.'); }
    finally { setBusy(false); }
  }
  useEffect(() => { load(); }, [token]);

  async function save() {
    try {
      await apiRequest('/allowances/budgets', { token, method: 'POST', body: JSON.stringify({ category_name: category, allocated_amount: amount, currency: 'USD' }) });
      setMessage('Budget saved in USD.'); load();
    } catch (error) { setMessage(error.message || 'Unable to save budget.'); }
  }

  return <ScrollView contentContainerStyle={styles.page}>
    <Text style={styles.eyebrow}>MONTHLY ENVELOPES</Text><Text style={styles.title}>Budgets</Text>
    {role === 'parent' && <View style={styles.form}><TextInput value={category} onChangeText={setCategory} placeholder="Category" style={styles.input} /><TextInput value={amount} onChangeText={setAmount} keyboardType="decimal-pad" placeholder="Allocation (USD)" style={styles.input} /><TouchableOpacity onPress={save} style={styles.button}><Text style={styles.buttonText}>Save budget</Text></TouchableOpacity></View>}
    {!!message && <Text style={styles.message}>{message}</Text>}
    {busy && <ActivityIndicator color="#006b52" />}
    {budgets.map((item) => { const allocated = Number(item.allocated_amount); const spent = Number(item.spent_amount); const percent = allocated ? Math.min(100, spent / allocated * 100) : 0; return <View style={styles.card} key={String(item.id)}><View style={styles.row}><Text style={styles.category}>{item.category_name}</Text><Text style={styles.money}>${spent.toFixed(2)} / ${allocated.toFixed(2)}</Text></View><View style={styles.track}><View style={[styles.fill, { width: `${percent}%` }]} /></View><Text style={styles.caption}>{item.currency} · {Math.max(0, allocated - spent).toFixed(2)} available</Text></View>; })}
    {!busy && budgets.length === 0 && <Text style={styles.caption}>No budget envelopes yet.</Text>}
  </ScrollView>;
}

const styles = StyleSheet.create({
  page: { padding: 22, paddingTop: 55, backgroundColor: '#f6f8f6', minHeight: '100%' }, eyebrow: { color: '#75817b', fontSize: 11, letterSpacing: 1.3, fontWeight: '700' }, title: { color: '#17231e', fontSize: 27, fontWeight: '800', marginTop: 8, marginBottom: 17 },
  form: { backgroundColor: '#fff', borderRadius: 15, padding: 14, marginBottom: 14 }, input: { padding: 12, borderColor: '#e7ece8', borderWidth: 1, borderRadius: 10, marginBottom: 8 }, button: { backgroundColor: '#006b52', borderRadius: 10, padding: 12, alignItems: 'center' }, buttonText: { color: '#fff', fontWeight: '700' },
  card: { backgroundColor: '#fff', padding: 15, borderRadius: 14, marginBottom: 10 }, row: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10 }, category: { color: '#26332c', fontSize: 13, fontWeight: '700' }, money: { color: '#75817b', fontSize: 11 }, track: { height: 7, backgroundColor: '#eef2ef', borderRadius: 9, overflow: 'hidden' }, fill: { height: '100%', backgroundColor: '#32876b', borderRadius: 9 }, caption: { color: '#75817b', fontSize: 11, marginTop: 7 }, message: { color: '#006b52', marginBottom: 10, fontSize: 12 },
});
