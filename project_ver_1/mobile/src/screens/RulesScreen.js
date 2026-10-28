import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { apiRequest } from '../services/api';

export default function RulesScreen({ token }) {
  const [rules, setRules] = useState([]);
  const [ruleText, setRuleText] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function load() {
    setBusy(true);
    try { setRules(await apiRequest('/guardrails/rules', { token })); }
    catch (error) { setMessage(error.message || 'Unable to load rules.'); }
    finally { setBusy(false); }
  }
  useEffect(() => { load(); }, [token]);

  async function save() {
    try {
      await apiRequest('/guardrails/rules', { token, method: 'POST', body: JSON.stringify({ rule_text: ruleText }) });
      setRuleText(''); setMessage('Spending rule saved.'); load();
    } catch (error) { setMessage(error.message || 'Unable to save rule.'); }
  }

  return <ScrollView contentContainerStyle={styles.page}>
    <Text style={styles.eyebrow}>PARENT CONTROLS</Text><Text style={styles.title}>Spending rules</Text>
    <Text style={styles.copy}>Rules flag transactions after PayPal processes them; they cannot block an external checkout.</Text>
    <TextInput value={ruleText} onChangeText={setRuleText} placeholder="Flag video game purchases over $25" multiline style={styles.input} />
    <TouchableOpacity onPress={save} style={styles.button}><Text style={styles.buttonText}>Add rule</Text></TouchableOpacity>
    {!!message && <Text style={styles.message}>{message}</Text>}
    <Text style={styles.heading}>Active family rules</Text>
    {busy && <ActivityIndicator color="#006b52" />}
    {rules.map((rule) => <View key={String(rule.id)} style={styles.rule}><Text style={styles.ruleText}>{rule.rule_text}</Text></View>)}
    {!busy && rules.length === 0 && <Text style={styles.copy}>No active rules yet.</Text>}
  </ScrollView>;
}

const styles = StyleSheet.create({
  page: { padding: 22, paddingTop: 55, backgroundColor: '#f6f8f6', minHeight: '100%' }, eyebrow: { color: '#75817b', fontSize: 11, letterSpacing: 1.3, fontWeight: '700' },
  title: { color: '#17231e', fontSize: 27, fontWeight: '800', marginTop: 8 }, copy: { color: '#75817b', fontSize: 12, lineHeight: 18, marginVertical: 12 }, input: { backgroundColor: '#fff', borderColor: '#e7ece8', borderWidth: 1, borderRadius: 12, padding: 14, minHeight: 90, textAlignVertical: 'top' },
  button: { backgroundColor: '#006b52', borderRadius: 12, padding: 14, alignItems: 'center', marginTop: 10 }, buttonText: { color: '#fff', fontWeight: '700' }, message: { color: '#006b52', marginTop: 12, fontSize: 12 }, heading: { color: '#17231e', fontSize: 16, fontWeight: '800', marginTop: 24, marginBottom: 10 },
  rule: { backgroundColor: '#fff', padding: 14, borderRadius: 12, marginBottom: 8 }, ruleText: { color: '#26332c', fontSize: 13 },
});
