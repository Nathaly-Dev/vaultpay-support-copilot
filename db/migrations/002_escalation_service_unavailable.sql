-- 002_escalation_service_unavailable.sql
-- Novo motivo de encaminhamento: o modelo de IA estava fora do ar.
-- Separado de 'low_confidence' para a análise distinguir "o sistema caiu" de "não sabia".
-- A 001 já foi aplicada e nunca é editada: mudança de schema é sempre uma migration nova.
-- Pode rodar mais de uma vez sem erro (remove e recria a mesma regra).

BEGIN;

ALTER TABLE escalations DROP CONSTRAINT IF EXISTS escalations_reason_check;

ALTER TABLE escalations ADD CONSTRAINT escalations_reason_check CHECK (
    reason IN ('no_context', 'low_confidence', 'user_requested', 'sensitive_topic', 'service_unavailable')
);

COMMIT;
