import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { apiRequest } from '../services/api';
import PurchaseRequestScreen from './PurchaseRequestScreen';

export default function PurchaseRequestsScreen({ role, token }) {
  const [requests, setRequests] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function load() {
    setBusy(true);
    try {
      setRequests(await apiRequest('/family/purchase-requests', { token }));
      setMessage('');
    } catch (error) {
      setMessage(error.message || 'Unable to load requests.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { load(); }, [token]);

  async function submit(payload) {
    try {
      await apiRequest('/family/purchase-requests', { token, method: 'POST', body: JSON.stringify(payload) });
      setShowForm(false);
      setMessage('Request sent to your parent.');
      load();
    } catch (error) {
      setMessage(error.message || 'Unable to submit request.');
    }
  }

  async function decide(id, action) {
    try {
      await apiRequest(`/family/purchase-requests/${id}/decision`, { token, method: 'POST', body: JSON.stringify({ action }) });
      setMessage(action === 'approve' ? 'Request approved; this does not charge PayPal.' : 'Request declined.');
      load();
    } catch (error) {
      setMessage(error.message || 'Unable to update request.');
    }
  }

  if (showForm) return <PurchaseRequestScreen onSubmit={submit} onCancel={() => setShowForm(false)} />;

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={styles.eyebrow}>FAMILY REQUESTS</Text><Text style={styles.title}>Purchase requests</Text>
      {role === 'child' && <TouchableOpacity style={styles.primary} onPress={() => setShowForm(true)}><Text style={styles.primaryText}>＋ New request</Text></TouchableOpacity>}
      {!!message && <Text style={styles.message}>{message}</Text>}
      {busy && <ActivityIndicator color="#006b52" />}
      {requests.map((item) => <View key={String(item.id)} style={styles.card}><View style={{ flex: 1 }}><Text style={styles.merchant}>{item.merchant}</Text><Text style={styles.caption}>${Number(item.amount).toFixed(2)} USD · {item.status}</Text>{item.note ? <Text style={styles.caption}>{item.note}</Text> : null}</View>{role === 'parent' && item.status === 'pending' && <View style={styles.actions}><Text onPress={() => decide(item.id, 'approve')} style={styles.approve}>Approve</Text><Text onPress={() => decide(item.id, 'decline')} style={styles.decline}>Decline</Text></View>}</View>)}
      {!busy && requests.length === 0 && <Text style={styles.caption}>No requests yet.</Text>}
      <Text style={styles.disclaimer}>Approving is a family decision record only. No PayPal order or payment is created.</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 22, paddingTop: 55, backgroundColor: '#f6f8f6', minHeight: '100%' }, eyebrow: { color: '#75817b', fontSize: 11, letterSpacing: 1.3, fontWeight: '700' },
  title: { color: '#17231e', fontSize: 27, fontWeight: '800', marginTop: 8, marginBottom: 18 }, primary: { backgroundColor: '#006b52', padding: 13, borderRadius: 12, alignItems: 'center', marginBottom: 12 }, primaryText: { color: '#fff', fontWeight: '700' },
  card: { backgroundColor: '#fff', padding: 15, borderRadius: 14, marginBottom: 10, flexDirection: 'row', alignItems: 'center', gap: 12 }, merchant: { color: '#26332c', fontSize: 14, fontWeight: '700' }, caption: { color: '#75817b', fontSize: 11, marginTop: 5 }, actions: { gap: 10 }, approve: { color: '#006b52', fontWeight: '700', fontSize: 12 }, decline: { color: '#b64040', fontWeight: '700', fontSize: 12 },
  message: { color: '#006b52', marginBottom: 12, fontSize: 12 }, disclaimer: { color: '#8a6a39', backgroundColor: '#fff6e8', padding: 13, borderRadius: 12, fontSize: 11, lineHeight: 16, marginTop: 10 },
});
