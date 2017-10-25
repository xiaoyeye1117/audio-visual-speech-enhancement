import os

from keras import optimizers, regularizers
from keras.layers import Input, Dense, Convolution2D, MaxPooling2D, Deconvolution2D
from keras.layers import Dropout, Flatten, BatchNormalization, LeakyReLU, Reshape
from keras.layers.merge import concatenate
from keras.models import Model, load_model
from keras.callbacks import TensorBoard, EarlyStopping, ModelCheckpoint

import numpy as np


class SpeechEnhancementNetwork(object):

	def __init__(self, model):
		self.__model = model

	@classmethod
	def build(cls, audio_spectrogram_shape, video_shape):
		# append channels axis
		extended_audio_spectrogram_shape = list(audio_spectrogram_shape)
		extended_audio_spectrogram_shape.append(1)

		encoder, shared_embedding_size, audio_embedding_shape, video_embedding_shape = cls.__build_encoder(
			extended_audio_spectrogram_shape, video_shape
		)

		decoder = cls.__build_decoder(shared_embedding_size, audio_embedding_shape, video_embedding_shape, video_shape)

		audio_input = Input(shape=extended_audio_spectrogram_shape)
		video_input = Input(shape=video_shape)

		model = Model(inputs=[audio_input, video_input], outputs=decoder(encoder([audio_input, video_input])))

		optimizer = optimizers.adam(lr=5e-4)
		model.compile(loss='mean_squared_error', optimizer=optimizer)

		model.summary()

		return SpeechEnhancementNetwork(model)

	@classmethod
	def __build_encoder(cls, extended_audio_spectrogram_shape, video_shape):
		audio_input = Input(shape=extended_audio_spectrogram_shape)
		video_input = Input(shape=video_shape)

		audio_embedding_matrix = cls.__build_audio_encoder(audio_input)
		audio_embedding = Flatten()(audio_embedding_matrix)

		video_embedding_matrix = cls.__build_video_encoder(video_input)
		video_embedding = Flatten()(video_embedding_matrix)

		x = concatenate([audio_embedding, video_embedding])
		shared_embedding_size = int(x._keras_shape[1] / 2)

		x = Dense(shared_embedding_size)(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)
		# x = Dropout(0.1)(x)

		x = Dense(shared_embedding_size)(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)
		# x = Dropout(0.1)(x)

		shared_embedding = Dense(shared_embedding_size)(x)

		model = Model(inputs=[audio_input, video_input], outputs=shared_embedding)
		model.summary()

		return model, shared_embedding_size, audio_embedding_matrix.shape[1:].as_list(), video_embedding_matrix.shape[1:].as_list()

	@classmethod
	def __build_decoder(cls, shared_embedding_size, audio_embedding_shape, video_embedding_shape, video_shape):
		shared_embedding_input = Input(shape=(shared_embedding_size,))

		x = Dense(shared_embedding_size)(shared_embedding_input)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)
		# x = Dropout(0.1)(x)

		x = Dense(shared_embedding_size)(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)
		# x = Dropout(0.1)(x)

		audio_embedding_size = np.prod(audio_embedding_shape)
		# video_embedding_size = np.prod(video_embedding_shape)

		a = Dense(audio_embedding_size)(x)
		a = Reshape(audio_embedding_shape)(a)
		a = BatchNormalization()(a)
		audio_embedding = LeakyReLU()(a)
		# audio_embedding = Dropout(0.1)(a)

		# v = Dense(video_embedding_size)(x)
		# v = Reshape(video_embedding_shape)(v)
		# v = BatchNormalization()(v)
		# v = LeakyReLU()(v)
		# video_embedding = Dropout(0.1)(v)

		audio_output = cls.__build_audio_decoder(audio_embedding)
		# video_output = cls.__build_video_decoder(video_embedding, video_shape)

		model = Model(inputs=shared_embedding_input, outputs=audio_output)
		model.summary()

		return model

	@staticmethod
	def __build_audio_encoder(audio_input):
		x = Convolution2D(8, kernel_size=(5, 5), strides=(2, 2), padding='same')(audio_input)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)

		x = Convolution2D(8, kernel_size=(4, 4), strides=(1, 1), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)

		x = Convolution2D(16, kernel_size=(4, 4), strides=(2, 2), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)

		x = Convolution2D(32, kernel_size=(2, 2), strides=(2, 1), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)

		x = Convolution2D(32, kernel_size=(2, 2), strides=(2, 1), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)

		x = Convolution2D(64, kernel_size=(1, 1), strides=(1, 1), padding='same')(x)

		return x

	@staticmethod
	def __build_audio_decoder(embedding):
		x = Deconvolution2D(64, kernel_size=(1, 1), strides=(1, 1), padding='same')(embedding)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)

		x = Deconvolution2D(32, kernel_size=(2, 2), strides=(2, 1), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)

		x = Deconvolution2D(32, kernel_size=(2, 2), strides=(2, 1), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)

		x = Deconvolution2D(16, kernel_size=(4, 4), strides=(2, 2), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)

		x = Deconvolution2D(8, kernel_size=(4, 4), strides=(1, 1), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)

		x = Deconvolution2D(8, kernel_size=(5, 5), strides=(2, 2), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)

		x = Deconvolution2D(1, kernel_size=(1, 1), strides=(1, 1), padding='same')(x)

		return x

	@staticmethod
	def __build_video_encoder(video_input):
		x = Convolution2D(128, kernel_size=(5, 5), padding='same')(video_input)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)
		x = MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same')(x)
		x = Dropout(0.25)(x)

		x = Convolution2D(128, kernel_size=(5, 5), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)
		x = MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same')(x)
		x = Dropout(0.25)(x)

		x = Convolution2D(256, kernel_size=(3, 3), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)
		x = MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same')(x)
		x = Dropout(0.25)(x)

		x = Convolution2D(256, kernel_size=(3, 3), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)
		x = MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same')(x)
		x = Dropout(0.25)(x)

		x = Convolution2D(512, kernel_size=(3, 3), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)
		x = MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same')(x)
		x = Dropout(0.25)(x)

		x = Convolution2D(512, kernel_size=(3, 3), padding='same')(x)
		x = BatchNormalization()(x)
		x = LeakyReLU()(x)
		x = MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same')(x)
		x = Dropout(0.25)(x)

		x = Convolution2D(512, kernel_size=(3, 3), padding='same')(x)

		return x

	# @staticmethod
	# def __build_video_decoder(embedding, video_shape):
	# 	x = Deconvolution2D(512, kernel_size=(3, 3), padding='same')(embedding)
	# 	x = BatchNormalization()(x)
	# 	x = LeakyReLU()(x)
	# 	x = Dropout(0.1)(x)
	#
	# 	x = Deconvolution2D(512, kernel_size=(3, 3), strides=(2, 2), padding='same')(x)
	# 	x = BatchNormalization()(x)
	# 	x = LeakyReLU()(x)
	# 	x = Dropout(0.1)(x)
	#
	# 	x = Deconvolution2D(512, kernel_size=(3, 3), strides=(2, 2), padding='same')(x)
	# 	x = BatchNormalization()(x)
	# 	x = LeakyReLU()(x)
	# 	x = Dropout(0.1)(x)
	#
	# 	x = Deconvolution2D(256, kernel_size=(3, 3), strides=(2, 2), padding='same')(x)
	# 	x = BatchNormalization()(x)
	# 	x = LeakyReLU()(x)
	# 	x = Dropout(0.1)(x)
	#
	# 	x = Deconvolution2D(256, kernel_size=(3, 3), strides=(2, 2), padding='same')(x)
	# 	x = BatchNormalization()(x)
	# 	x = LeakyReLU()(x)
	# 	x = Dropout(0.1)(x)
	#
	# 	x = Deconvolution2D(128, kernel_size=(5, 5), strides=(2, 2), padding='same')(x)
	# 	x = BatchNormalization()(x)
	# 	x = LeakyReLU()(x)
	# 	x = Dropout(0.1)(x)
	#
	# 	x = Deconvolution2D(128, kernel_size=(5, 5), strides=(2, 2), padding='same')(x)
	# 	x = BatchNormalization()(x)
	# 	x = LeakyReLU()(x)
	# 	x = Dropout(0.1)(x)
	#
	# 	x = Deconvolution2D(video_shape[-1], kernel_size=(1, 1), strides=(1, 1), padding='same')(x)
	#
	# 	return x

	def train(self, mixed_spectrograms, input_video_samples, speech_spectrograms,
			  model_cache_dir, tensorboard_dir):

		mixed_spectrograms = np.expand_dims(mixed_spectrograms, -1)  # append channels axis
		speech_spectrograms = np.expand_dims(speech_spectrograms, -1)  # append channels axis

		model_cache = ModelCache(model_cache_dir)
		checkpoint = ModelCheckpoint(model_cache.auto_encoder_path(), verbose=1)

		early_stopping = EarlyStopping(monitor='val_loss', min_delta=0.01, patience=10, verbose=1)
		tensorboard = TensorBoard(log_dir=tensorboard_dir, histogram_freq=0, write_graph=True, write_images=True)

		self.__model.fit(
			x=[mixed_spectrograms, input_video_samples],
			y=speech_spectrograms,
			validation_split=0.1, batch_size=16, epochs=1000,
			callbacks=[checkpoint, early_stopping, tensorboard],
			verbose=1
		)

	def predict(self, mixed_spectrograms, video_samples):
		mixed_spectrograms = np.expand_dims(mixed_spectrograms, -1)  # append channels axis
		speech_spectrograms = self.__model.predict([mixed_spectrograms, video_samples])

		return np.squeeze(speech_spectrograms)

	@staticmethod
	def load(model_cache_dir):
		model_cache = ModelCache(model_cache_dir)
		auto_encoder = load_model(model_cache.auto_encoder_path())

		return SpeechEnhancementNetwork(auto_encoder)

	def save(self, model_cache_dir):
		model_cache = ModelCache(model_cache_dir)

		self.__model.save(model_cache.auto_encoder_path())


class ModelCache(object):

	def __init__(self, cache_dir):
		self.__cache_dir = cache_dir

	def auto_encoder_path(self):
		return os.path.join(self.__cache_dir, "auto_encoder.h5py")
