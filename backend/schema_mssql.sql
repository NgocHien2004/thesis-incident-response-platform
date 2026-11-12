-- Sinh tự động từ các model SQLAlchemy cho SQL Server; ứng dụng cũng tự tạo bảng khi khởi động (create_all)

CREATE TABLE attack_types (
	code NVARCHAR(50) NOT NULL, 
	name_vi NVARCHAR(100) NOT NULL, 
	is_active BIT NOT NULL, 
	PRIMARY KEY (code)
);
GO

CREATE TABLE users (
	id INTEGER NOT NULL IDENTITY, 
	username NVARCHAR(50) NOT NULL, 
	password_hash NVARCHAR(255) NOT NULL, 
	full_name NVARCHAR(100) NOT NULL, 
	role NVARCHAR(30) NOT NULL, 
	is_active BIT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
);
GO

CREATE INDEX ix_users_id ON users (id);
GO

CREATE TABLE models (
	id INTEGER NOT NULL IDENTITY, 
	name NVARCHAR(100) NOT NULL, 
	version NVARCHAR(50) NOT NULL, 
	task_type NVARCHAR(20) NOT NULL, 
	file_path NVARCHAR(500) NULL, 
	preprocessor_path NVARCHAR(500) NULL, 
	metrics_json NTEXT NULL, 
	feature_names NTEXT NULL, 
	trained_at DATETIME NULL, 
	is_active BIT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_models_task_version UNIQUE (task_type, version)
);
GO

CREATE INDEX ix_models_id ON models (id);
GO

CREATE TABLE labels (
	id INTEGER NOT NULL IDENTITY, 
	data_type NVARCHAR(20) NOT NULL, 
	code NVARCHAR(100) NOT NULL, 
	name_vi NVARCHAR(150) NOT NULL, 
	is_dangerous BIT NOT NULL, 
	is_active BIT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_labels_type_code UNIQUE (data_type, code)
);
GO

CREATE INDEX ix_labels_id ON labels (id);
GO

CREATE TABLE settings (
	[key] NVARCHAR(100) NOT NULL, 
	value NVARCHAR(500) NOT NULL, 
	description NVARCHAR(300) NULL, 
	updated_at DATETIME NOT NULL, 
	updated_by INTEGER NULL, 
	PRIMARY KEY ([key]), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);
GO

CREATE TABLE incidents (
	id INTEGER NOT NULL IDENTITY, 
	code NVARCHAR(30) NOT NULL, 
	title NVARCHAR(200) NOT NULL, 
	description NTEXT NULL, 
	attack_type NVARCHAR(50) NOT NULL, 
	severity NVARCHAR(20) NOT NULL, 
	occurred_at DATETIME NOT NULL, 
	source NVARCHAR(30) NOT NULL, 
	status NVARCHAR(20) NOT NULL, 
	created_by INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	resolved_at DATETIME NULL, 
	closed_at DATETIME NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	FOREIGN KEY(attack_type) REFERENCES attack_types (code), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);
GO

CREATE INDEX ix_incidents_attack_type ON incidents (attack_type);
GO

CREATE INDEX ix_incidents_id ON incidents (id);
GO

CREATE INDEX ix_incidents_occurred_at ON incidents (occurred_at);
GO

CREATE INDEX ix_incidents_status ON incidents (status);
GO

CREATE TABLE incident_status_history (
	id INTEGER NOT NULL IDENTITY, 
	incident_id INTEGER NOT NULL, 
	old_status NVARCHAR(20) NULL, 
	new_status NVARCHAR(20) NOT NULL, 
	changed_by INTEGER NOT NULL, 
	changed_at DATETIME NOT NULL, 
	note NTEXT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(incident_id) REFERENCES incidents (id), 
	FOREIGN KEY(changed_by) REFERENCES users (id)
);
GO

CREATE INDEX ix_incident_status_history_id ON incident_status_history (id);
GO

CREATE INDEX ix_incident_status_history_incident_id ON incident_status_history (incident_id);
GO

CREATE TABLE uploads (
	id INTEGER NOT NULL IDENTITY, 
	incident_id INTEGER NOT NULL, 
	original_filename NVARCHAR(255) NOT NULL, 
	stored_path NVARCHAR(500) NOT NULL, 
	file_hash VARCHAR(64) NOT NULL, 
	data_type NVARCHAR(20) NOT NULL, 
	file_size_bytes BIGINT NOT NULL, 
	row_count INTEGER NULL, 
	processed_rows INTEGER NOT NULL, 
	status NVARCHAR(20) NOT NULL, 
	error_message NTEXT NULL, 
	model_id INTEGER NULL, 
	threshold_used FLOAT NULL, 
	dangerous_labels_used NTEXT NULL, 
	alert_count INTEGER NOT NULL, 
	avg_confidence FLOAT NULL, 
	label_distribution NTEXT NULL, 
	uploaded_by INTEGER NOT NULL, 
	uploaded_at DATETIME NOT NULL, 
	processed_at DATETIME NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(incident_id) REFERENCES incidents (id), 
	FOREIGN KEY(model_id) REFERENCES models (id), 
	FOREIGN KEY(uploaded_by) REFERENCES users (id)
);
GO

CREATE INDEX ix_uploads_id ON uploads (id);
GO

CREATE INDEX ix_uploads_incident_hash ON uploads (incident_id, file_hash);
GO

CREATE TABLE alerts (
	id INTEGER NOT NULL IDENTITY, 
	incident_id INTEGER NULL, 
	upload_id INTEGER NOT NULL, 
	row_index INTEGER NOT NULL, 
	predicted_label NVARCHAR(100) NOT NULL, 
	confidence FLOAT NOT NULL, 
	source_type NVARCHAR(20) NOT NULL, 
	row_data NTEXT NULL, 
	auto_linked BIT NOT NULL, 
	linked_at DATETIME NULL, 
	verification_status NVARCHAR(20) NOT NULL, 
	verified_by INTEGER NULL, 
	verified_at DATETIME NULL, 
	note NTEXT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_alerts_upload_row UNIQUE (upload_id, row_index), 
	FOREIGN KEY(incident_id) REFERENCES incidents (id), 
	FOREIGN KEY(upload_id) REFERENCES uploads (id), 
	FOREIGN KEY(verified_by) REFERENCES users (id)
);
GO

CREATE INDEX ix_alerts_id ON alerts (id);
GO

CREATE INDEX ix_alerts_incident ON alerts (incident_id);
GO

CREATE INDEX ix_alerts_label ON alerts (predicted_label);
GO

CREATE INDEX ix_alerts_verification ON alerts (verification_status);
GO

CREATE TABLE alert_move_history (
	id INTEGER NOT NULL IDENTITY, 
	alert_id INTEGER NOT NULL, 
	from_incident_id INTEGER NULL, 
	to_incident_id INTEGER NULL, 
	moved_by INTEGER NOT NULL, 
	moved_at DATETIME NOT NULL, 
	reason NTEXT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(alert_id) REFERENCES alerts (id), 
	FOREIGN KEY(from_incident_id) REFERENCES incidents (id), 
	FOREIGN KEY(to_incident_id) REFERENCES incidents (id), 
	FOREIGN KEY(moved_by) REFERENCES users (id)
);
GO

CREATE INDEX ix_alert_move_history_alert_id ON alert_move_history (alert_id);
GO

CREATE INDEX ix_alert_move_history_id ON alert_move_history (id);
GO
